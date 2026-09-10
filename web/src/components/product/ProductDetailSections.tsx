"use client";

import { useTranslations } from "next-intl";

import { Switch } from "@/components/ui/switch";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { localeValue } from "@/lib/locale";
import { VariantCard } from "@/components/product/VariantCard";
import type { ProductResponse, ProductVariantResponse } from "@/types/product";

export interface AttributeMaps {
  enAttrMap: Map<string, string>;
  arAttrMap: Map<string, string>;
  enOptionMap: Map<string, string>;
  arOptionMap: Map<string, string>;
}

export interface GroupedAttribute {
  id: string;
  attribute_id: string;
  value: string | null;
  values: (string | null)[];
}

interface ProductDetailSectionsProps {
  product: ProductResponse;
  locale: string;
  longDesc: string;
  longDescAr: string;
  attributeMaps: AttributeMaps;
  groupedAttributes: GroupedAttribute[];
  visibleVariants: ProductVariantResponse[] | undefined;
  totalVariants: number;
  inactiveCount: number;
  showInactiveVariants: boolean;
  onToggleInactiveVariants: (checked: boolean) => void;
}

function resolveValue(value: string | null, optionMap: Map<string, string>): string {
  if (!value) return "—";
  try {
    const parsed = JSON.parse(value);
    if (Array.isArray(parsed)) {
      if (parsed.length > 0 && typeof parsed[0] === "object" && "material" in parsed[0]) {
        return parsed
          .map(
            (entry: { material: string; percentage: number }) =>
              `${optionMap.get(entry.material) ?? entry.material.slice(0, 8)} ${entry.percentage}%`,
          )
          .join(", ");
      }
      return parsed.map((id: string) => optionMap.get(id) ?? id.slice(0, 8)).join(", ");
    }
  } catch (error_) {
    console.warn("Failed to parse attribute value:", error_);
  }
  return optionMap.get(value) ?? value.slice(0, 8);
}

export function ProductDetailSections({
  product,
  locale,
  longDesc,
  longDescAr,
  attributeMaps,
  groupedAttributes,
  visibleVariants,
  totalVariants,
  inactiveCount,
  showInactiveVariants,
  onToggleInactiveVariants,
}: ProductDetailSectionsProps) {
  const t = useTranslations("product");
  const { enAttrMap, arAttrMap, enOptionMap, arOptionMap } = attributeMaps;

  return (
    <>
      {longDesc && (
        <section className="space-y-2">
          <h2 className="text-lg font-semibold">{t("description")}</h2>
          <p className="text-muted-foreground text-sm leading-relaxed whitespace-pre-line">
            {longDesc}
          </p>
        </section>
      )}
      {longDescAr && (
        <section className="space-y-2">
          <h2 className="text-lg font-semibold" dir="rtl">
            {t("description")}
          </h2>
          <p
            className="text-muted-foreground text-sm leading-relaxed whitespace-pre-line"
            dir="rtl"
          >
            {longDescAr}
          </p>
        </section>
      )}

      {product.is_multi_piece && product.pieces && product.pieces.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold">{t("pieces")}</h2>
          <div className="flex flex-wrap gap-3">
            {product.pieces.map((piece) => (
              <div key={piece.id} className="bg-muted/30 rounded-xl border px-4 py-2 text-sm">
                {piece.name_en || t("unnamed")}
              </div>
            ))}
          </div>
        </section>
      )}

      {product.is_multi_piece && product.color_sets && product.color_sets.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold">
            {t("colorSetsCount", { count: product.color_sets.length })}
          </h2>
          <div className="flex flex-wrap gap-3">
            {product.color_sets.map((cs) => (
              <div
                key={cs.id}
                className="bg-muted/30 flex items-center gap-4 rounded-xl border p-3"
              >
                {cs.values.map((val) => (
                  <div key={val.id} className="flex items-center gap-2">
                    {val.color_option?.color_hex && (
                      <span
                        className="inline-block size-6 shrink-0 rounded-full border"
                        style={{ backgroundColor: val.color_option.color_hex }}
                      />
                    )}
                    <div>
                      <p className="text-xs font-medium">{val.piece_name_en || t("piece")}</p>
                      <p className="text-muted-foreground text-xs">
                        {val.color_option
                          ? localeValue(
                              locale,
                              val.color_option.value_ar,
                              val.color_option.value_fa,
                              val.color_option.value_en,
                            )
                          : "—"}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </section>
      )}

      {product.variants && product.variants.length > 0 && (
        <section className="space-y-3">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold">
              {t("variants")} ({visibleVariants?.length ?? 0}/{totalVariants})
            </h2>
            {inactiveCount > 0 && (
              <label className="text-muted-foreground flex items-center gap-1.5 text-xs">
                <Switch
                  size="sm"
                  checked={showInactiveVariants}
                  onCheckedChange={onToggleInactiveVariants}
                />
                {t("showInactive")}
              </label>
            )}
          </div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {visibleVariants?.map((v) => (
              <VariantCard key={v.id} variant={v} />
            ))}
          </div>
        </section>
      )}

      {product.attribute_values && product.attribute_values.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold">{t("attributes")}</h2>
          <Accordion multiple defaultValue={[]}>
            <AccordionItem value="en">
              <AccordionTrigger>{t("attributesEnglish")}</AccordionTrigger>
              <AccordionContent>
                <div className="divide-y">
                  {groupedAttributes.map((av) => (
                    <div key={av.id} className="flex items-baseline gap-2 py-2">
                      <span className="text-muted-foreground shrink-0 text-xs font-medium tracking-wide uppercase">
                        {enAttrMap.get(av.attribute_id) ?? av.attribute_id.slice(0, 8)}:
                      </span>
                      <span className="min-w-0 text-sm break-words">
                        {av.values.map((v) => resolveValue(v, enOptionMap)).join(", ")}
                      </span>
                    </div>
                  ))}
                </div>
              </AccordionContent>
            </AccordionItem>
            <AccordionItem value="ar">
              <AccordionTrigger>{t("attributesArabic")}</AccordionTrigger>
              <AccordionContent>
                <div className="divide-y" dir="rtl">
                  {groupedAttributes.map((av) => (
                    <div key={av.id} className="flex items-baseline gap-2 py-2">
                      <span className="text-muted-foreground shrink-0 text-xs font-medium tracking-wide uppercase">
                        {arAttrMap.get(av.attribute_id) ||
                          enAttrMap.get(av.attribute_id) ||
                          av.attribute_id.slice(0, 8)}
                        :
                      </span>
                      <span className="min-w-0 text-sm break-words">
                        {av.values.map((v) => resolveValue(v, arOptionMap)).join("، ")}
                      </span>
                    </div>
                  ))}
                </div>
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </section>
      )}

      {product.sizes && product.sizes.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold">{t("sizes")}</h2>
          <div className="flex flex-wrap gap-2">
            {product.sizes.map((s) => (
              <span key={s.id} className="bg-muted rounded-lg border px-3 py-1.5 text-sm">
                {s.size_label} <span className="text-muted-foreground">({s.stock})</span>
              </span>
            ))}
          </div>
        </section>
      )}

      <div className="text-muted-foreground border-t pt-4 text-xs">
        <p>
          {t("idLabel")}: {product.id}
        </p>
        <p>
          {t("updatedLabel")}: {new Date(product.updated_at).toLocaleString()}
        </p>
      </div>
    </>
  );
}
