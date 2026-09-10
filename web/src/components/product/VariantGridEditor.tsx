"use client";

import { useMemo, useCallback, useEffect, useRef } from "react";
import { useTranslations, useLocale } from "next-intl";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";
import { localeValue } from "@/lib/locale";
import type {
  AttributeItem,
  AttributeOptionItem,
  ProductVariantInput,
  ProductColorSetInput,
} from "@/types/api";

interface VariantGridEditorProps {
  attributes: AttributeItem[];
  selectedOptionIds: Record<string, string[]>;
  optionsMap: Record<string, AttributeOptionItem[]>;
  variants: ProductVariantInput[];
  onChange: (variants: ProductVariantInput[]) => void;
  defaultQuantity: number;
  locale: string;
  currencySymbol: string;
  isMultiPiece?: boolean | undefined;
  colorSets?: ProductColorSetInput[] | undefined;
}

function findOption(
  optionId: string,
  optionsMap: Record<string, AttributeOptionItem[]>,
): AttributeOptionItem | undefined {
  for (const opts of Object.values(optionsMap)) {
    const opt = opts.find((o) => o.id === optionId);
    if (opt) return opt;
  }
  return undefined;
}

function getOptionLabel(
  optionId: string,
  optionsMap: Record<string, AttributeOptionItem[]>,
  locale: string,
): string {
  const opt = findOption(optionId, optionsMap);
  if (!opt) return optionId;
  return localeValue(locale, opt.value_ar, opt.value_fa, opt.value_en);
}

function colorCircleStyle(colorHex: string | null): React.CSSProperties {
  if (colorHex === "#FF00FF") {
    return {
      background:
        "conic-gradient(red, #ff8000, yellow, #80ff00, lime, #00ff80, aqua, #0080ff, blue, #8000ff, magenta, #ff0080, red)",
    };
  }
  return { backgroundColor: colorHex || "#ccc" };
}

function variantKey(optionIds: string[], colorSetIdx: number | undefined): string {
  const parts = colorSetIdx == null ? [] : [`cs_${colorSetIdx}`];
  parts.push(...optionIds);
  return [...parts].toSorted((a, b) => a.localeCompare(b)).join(",");
}

export function VariantGridEditor({
  attributes,
  selectedOptionIds,
  optionsMap,
  variants,
  onChange,
  defaultQuantity,
  locale,
  currencySymbol,
  isMultiPiece,
  colorSets = [],
}: VariantGridEditorProps) {
  const t = useTranslations("product");
  const contextLocale = useLocale();

  const variantDefiningAttrs = useMemo(
    () =>
      attributes.filter(
        (a) => a.is_variant_defining && !(isMultiPiece && a.code === "primary_color"),
      ),
    [attributes, isMultiPiece],
  );

  const attrOptionGroups = useMemo(() => {
    const groups: { attr: AttributeItem; ids: string[] }[] = [];
    for (const attr of variantDefiningAttrs) {
      const ids = selectedOptionIds[attr.id] ?? [];
      if (ids.length > 0) {
        groups.push({ attr, ids });
      }
    }
    return groups;
  }, [variantDefiningAttrs, selectedOptionIds]);

  const colorSetGroups = useMemo(() => {
    if (!isMultiPiece || colorSets.length === 0) return null;
    return colorSets.map((cs, i) => ({
      index: i,
      colors: cs.values.map((v) => {
        const opt = findOption(v.color_option_id, optionsMap);
        return {
          label: opt ? localeValue(contextLocale, opt.value_ar, opt.value_fa, opt.value_en) : "?",
          hex: opt?.color_hex ?? null,
        };
      }),
    }));
  }, [isMultiPiece, colorSets, optionsMap, contextLocale]);

  const combinations = useMemo(() => {
    if (!colorSetGroups && attrOptionGroups.length === 0) return [];
    type ComboItem = {
      attrCode: string;
      optionId: string;
      optionLabel: string;
      colorHex: string | null;
    };
    const result: { colorSetIdx: number | undefined; items: ComboItem[] }[] = [];

    function cartesianAttr(
      index: number,
      current: ComboItem[],
      onComplete: (items: ComboItem[]) => void,
    ) {
      if (index === attrOptionGroups.length) {
        onComplete([...current]);
        return;
      }
      const group = attrOptionGroups[index];
      if (!group) return;
      for (const optionId of group.ids) {
        const opt = findOption(optionId, optionsMap);
        const optionLabel = getOptionLabel(optionId, optionsMap, locale);
        current.push({
          attrCode: group.attr.code,
          optionId,
          optionLabel,
          colorHex: opt?.color_hex ?? null,
        });
        cartesianAttr(index + 1, current, onComplete);
        current.pop();
      }
    }

    if (colorSetGroups) {
      for (const csg of colorSetGroups) {
        cartesianAttr(0, [], (items) => {
          result.push({ colorSetIdx: csg.index, items });
        });
      }
    } else {
      cartesianAttr(0, [], (items) => {
        result.push({ colorSetIdx: undefined, items });
      });
    }

    return result;
  }, [colorSetGroups, attrOptionGroups, optionsMap, locale]);

  const variantMap = useMemo(() => {
    const map = new Map<string, ProductVariantInput>();
    for (const v of variants) {
      const csIdx = v.color_set_id == null ? undefined : Number(v.color_set_id);
      const key = variantKey(v.attribute_option_ids, csIdx);
      map.set(key, v);
    }
    return map;
  }, [variants]);

  const allRows = useMemo(() => {
    const result = [...combinations];
    const coveredKeys = new Set(
      combinations.map((c) => {
        const ids = c.items.map((o) => o.optionId);
        if (c.colorSetIdx != null) ids.push(`cs_${c.colorSetIdx}`);
        return [...ids].toSorted((a, b) => a.localeCompare(b)).join(",");
      }),
    );
    for (const [key, v] of variantMap) {
      if (!coveredKeys.has(key)) {
        const csIdx = v.color_set_id == null ? undefined : Number(v.color_set_id);
        result.push({
          colorSetIdx: csIdx,
          items: v.attribute_option_ids.map((oid) => {
            const opt = findOption(oid, optionsMap);
            return {
              attrCode: opt?.code ?? "?",
              optionId: oid,
              optionLabel: getOptionLabel(oid, optionsMap, locale),
              colorHex: opt?.color_hex ?? null,
            };
          }),
        });
        coveredKeys.add(key);
      }
    }
    return result;
  }, [combinations, variantMap, optionsMap, locale]);

  const getOrCreateVariant = useCallback(
    (optionIds: string[], colorSetIdx: number | undefined): ProductVariantInput => {
      const key = variantKey(optionIds, colorSetIdx);
      const existing = variantMap.get(key);
      if (existing) return existing;
      const colorSetId = colorSetIdx == null ? undefined : String(colorSetIdx);
      const item: ProductVariantInput = {
        sku: "",
        quantity: defaultQuantity,
        low_stock_threshold: 5,
        price: null,
        is_active: true,
        attribute_option_ids: optionIds,
      };
      if (colorSetId !== undefined) item.color_set_id = colorSetId;
      return item;
    },
    [variantMap, defaultQuantity],
  );

  const updateVariant = useCallback(
    (
      optionIds: string[],
      colorSetIdx: number | undefined,
      field: keyof ProductVariantInput,
      value: unknown,
    ) => {
      const existing = getOrCreateVariant(optionIds, colorSetIdx);
      const updated = { ...existing, [field]: value };
      const key = variantKey(optionIds, colorSetIdx);
      const newVariants = variants.filter((v) => {
        const k = variantKey(
          v.attribute_option_ids,
          v.color_set_id == null ? undefined : Number(v.color_set_id),
        );
        return k !== key;
      });
      newVariants.push(updated);
      onChange(newVariants);
    },
    [variants, getOrCreateVariant, onChange],
  );

  const prevCombosRef = useRef("");
  const variantsRef = useRef(variants);
  useEffect(() => {
    variantsRef.current = variants;
  }, [variants]);
  const variantMapRef = useRef(variantMap);
  useEffect(() => {
    variantMapRef.current = variantMap;
  }, [variantMap]);

  useEffect(() => {
    const comboKey = combinations
      .map((c) => {
        const ids = c.items.map((o) => o.optionId);
        if (c.colorSetIdx != null) ids.push(`cs_${c.colorSetIdx}`);
        return [...ids].toSorted((a, b) => a.localeCompare(b)).join(",");
      })
      .join("|");
    if (comboKey === prevCombosRef.current) return;
    prevCombosRef.current = comboKey;

    const currentVariants = variantsRef.current;
    const currentMap = variantMapRef.current;
    const missing: ProductVariantInput[] = [];
    for (const combo of combinations) {
      const optionIds = combo.items.map((c) => c.optionId);
      const key = variantKey(optionIds, combo.colorSetIdx);
      const covered =
        currentMap.has(key) ||
        currentVariants.some((v) => optionIds.every((id) => v.attribute_option_ids.includes(id)));
      if (covered) continue;
      const colorSetId = combo.colorSetIdx == null ? undefined : String(combo.colorSetIdx);
      const variant: ProductVariantInput = {
        sku: "",
        quantity: defaultQuantity,
        low_stock_threshold: 5,
        price: null,
        is_active: true,
        attribute_option_ids: optionIds,
      };
      if (colorSetId !== undefined) variant.color_set_id = colorSetId;
      missing.push(variant);
    }
    if (missing.length > 0) {
      onChange([...currentVariants, ...missing]);
    }
  }, [combinations, onChange, defaultQuantity]);

  if (!colorSetGroups && variantDefiningAttrs.length === 0) {
    return (
      <div className="text-muted-foreground py-8 text-center text-sm">
        {t("noVariantDefiningAttributes")}
      </div>
    );
  }

  if (allRows.length === 0) {
    return (
      <div className="text-muted-foreground py-8 text-center text-sm">
        {t("selectAttributesForVariants")}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {allRows.map((combo, idx) => {
        const optionIds = combo.items.map((c) => c.optionId);
        const variant = getOrCreateVariant(optionIds, combo.colorSetIdx);
        return (
          <div
            key={idx}
            className={cn(
              "border-border flex flex-col gap-3 rounded-lg border p-4 transition-opacity",
              !variant.is_active && "opacity-40",
            )}
          >
            {/* Header: combo label + toggle */}
            <div className="flex items-center justify-between">
              <div className="flex flex-wrap items-center gap-x-1.5 gap-y-1 text-sm font-medium">
                {combo.colorSetIdx != null && colorSetGroups && (
                  <span className="bg-primary/10 inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-semibold">
                    {colorSetGroups[combo.colorSetIdx]?.colors.map((c, ci) => (
                      <span key={ci} className="inline-flex items-center gap-1">
                        {ci > 0 && <span className="text-muted-foreground">+</span>}
                        {c.hex && (
                          <span
                            className="inline-block size-3 shrink-0 rounded-full border"
                            style={colorCircleStyle(c.hex)}
                          />
                        )}
                        {c.label}
                      </span>
                    ))}
                  </span>
                )}
                {combo.items.map((c, ci) => (
                  <span key={c.optionId} className="inline-flex items-center gap-1">
                    {ci > 0 || combo.colorSetIdx != null ? (
                      <span className="text-muted-foreground mx-0.5">/</span>
                    ) : null}
                    {c.colorHex && (
                      <span
                        className="inline-block size-3.5 shrink-0 rounded-full border"
                        style={colorCircleStyle(c.colorHex)}
                      />
                    )}
                    {c.optionLabel}
                  </span>
                ))}
              </div>
              <Switch
                checked={variant.is_active}
                onCheckedChange={(v) => updateVariant(optionIds, combo.colorSetIdx, "is_active", v)}
              />
            </div>
            {!variant.is_active && <span className="text-muted-foreground text-xs">Inactive</span>}

            {/* Fields */}
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div className="flex flex-col gap-1">
                <label className="text-muted-foreground text-xs">{t("sku")}</label>
                <Input
                  className={cn(
                    "h-9",
                    variant.is_active && !variant.sku.trim() && "border-destructive",
                  )}
                  placeholder="SKU"
                  value={variant.sku}
                  onChange={(e) =>
                    updateVariant(optionIds, combo.colorSetIdx, "sku", e.target.value)
                  }
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-muted-foreground text-xs">{t("quantity")}</label>
                <Input
                  className="h-9"
                  type="number"
                  placeholder={defaultQuantity.toString()}
                  value={variant.quantity}
                  onChange={(e) =>
                    updateVariant(
                      optionIds,
                      combo.colorSetIdx,
                      "quantity",
                      Number.parseInt(e.target.value) || 0,
                    )
                  }
                />
              </div>
              <div className="flex flex-col gap-2">
                <div className="flex items-center justify-between gap-2">
                  <label className="text-muted-foreground text-xs">{t("setCustomPrice")}</label>
                  <Switch
                    checked={variant.price !== null}
                    onCheckedChange={(v) =>
                      updateVariant(optionIds, combo.colorSetIdx, "price", v ? 0 : null)
                    }
                  />
                </div>
                {variant.price !== null && (
                  <div className="relative">
                    <span className="text-muted-foreground pointer-events-none absolute top-1/2 left-2 z-10 -translate-y-1/2 text-xs font-medium">
                      {currencySymbol}
                    </span>
                    <Input
                      className={cn(
                        "h-9 pl-7",
                        variant.is_active &&
                          (variant.price === null || variant.price === undefined) &&
                          "border-destructive",
                      )}
                      type="number"
                      step="0.01"
                      placeholder="0.00"
                      value={variant.price ?? ""}
                      onChange={(e) =>
                        updateVariant(
                          optionIds,
                          combo.colorSetIdx,
                          "price",
                          e.target.value ? Number.parseFloat(e.target.value) : null,
                        )
                      }
                    />
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })}
      <p className="text-muted-foreground text-xs">
        {combinations.length} {t("variantCount")}
      </p>
    </div>
  );
}
