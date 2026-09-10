"use client";

import { useState, useMemo } from "react";
import { useRouter } from "@/i18n/routing";
import { useTranslations, useLocale } from "next-intl";
import { useForm, useWatch } from "react-hook-form";
import { toast } from "sonner";
import { FiCheckCircle, FiChevronLeft, FiChevronRight } from "react-icons/fi";
import { cn } from "@/lib/utils";
import { localeValue } from "@/lib/locale";
import { buildProductPayload } from "@/lib/product-form";
import { extractApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { useProductFormData } from "@/hooks/useProductFormData";
import { useGetStoreQuery } from "@/store/api/storeApi";
import { useGetCategoryTreeQuery } from "@/store/api/productApi";
import { BasicInfoStep } from "@/components/product/steps/BasicInfoStep";
import { DescriptionStep } from "@/components/product/steps/DescriptionStep";
import { AttributesStep } from "@/components/product/steps/AttributesStep";
import { CompositeColorSetsEditor } from "@/components/product/steps/CompositeColorSetsEditor";
import { PriceInventoryStep } from "@/components/product/steps/PriceInventoryStep";
import { MediaStep } from "@/components/product/steps/MediaStep";
import { ReviewStep } from "@/components/product/steps/ReviewStep";
import type {
  ProductResponse,
  ProductVariantInput,
  ProductPieceInput,
  ProductColorSetInput,
  CategoryNode,
} from "@/types/api";
import type { ImageUploadItem } from "./ProductImageUploader";

interface ProductFormProps {
  storeId: string;
  initialData?: ProductResponse;
  onSuccess?: () => void;
}

const ATTR_STEP_OFFSET = 2;

function buildAttributeDefaults(
  initialData: ProductResponse,
  defaultValues: Record<string, string>,
): void {
  const attrValueMap: Record<string, string[]> = {};
  for (const av of initialData.attribute_values || []) {
    if (!av.value) continue;
    const arr = attrValueMap[av.attribute_id];
    if (arr) {
      arr.push(av.value);
    } else {
      attrValueMap[av.attribute_id] = [av.value];
    }
  }
  for (const [attrId, values] of Object.entries(attrValueMap)) {
    if (values.length > 1) {
      const flat = values.flatMap((v) => {
        try {
          const p = JSON.parse(v);
          return Array.isArray(p) ? p : [v];
        } catch (error) {
          console.warn("Failed to parse multi-select value:", error);
          return [v];
        }
      });
      defaultValues[`attr_${attrId}`] = JSON.stringify([...new Set(flat)]);
    } else {
      defaultValues[`attr_${attrId}`] = values[0] ?? "";
    }
  }
}

export function ProductForm({ storeId, initialData, onSuccess }: ProductFormProps) {
  const router = useRouter();
  const t = useTranslations("product");
  const locale = useLocale();
  const isEdit = !!initialData;
  const [step, setStep] = useState(0);
  const [images, setImages] = useState<ImageUploadItem[]>(() => {
    const variantSigMap: Record<string, string[]> = {};
    for (const v of initialData?.variants || []) {
      variantSigMap[v.id] = v.attribute_options.map((o) => o.id);
    }
    return (
      initialData?.images?.map((img) => ({
        id: img.id,
        image_url: img.image_url,
        view_type_id: img.view_type_id,
        variant_signature: img.variant_id ? (variantSigMap[img.variant_id] ?? null) : null,
        alt_text_ar: img.alt_text_ar || "",
        alt_text_en: img.alt_text_en || "",
        alt_text_fa: img.alt_text_fa || "",
        sort_order: img.sort_order,
      })) || []
    );
  });

  const [mediaError, setMediaError] = useState<string | null>(null);
  const [variantError, setVariantError] = useState<string | null>(null);
  const [variants, setVariants] = useState<ProductVariantInput[]>(() => {
    if (!initialData?.variants) return [];
    const csIdToIdx: Record<string, number> = {};
    if (initialData.color_sets) {
      for (const cs of initialData.color_sets) {
        csIdToIdx[cs.id] = cs.sort_order;
      }
    }
    return initialData.variants.map((v) => {
      const item: ProductVariantInput = {
        sku: v.sku,
        barcode: v.barcode,
        price: v.price,
        original_price: v.original_price,
        sale_price: v.sale_price,
        quantity: v.quantity,
        low_stock_threshold: v.low_stock_threshold,
        weight: v.weight,
        is_active: v.is_active,
        attribute_option_ids: v.attribute_options.map((o) => o.id),
      };
      if (v.color_set_id) {
        item.color_set_id = csIdToIdx[v.color_set_id]?.toString() ?? v.color_set_id;
      }
      return item;
    });
  });

  const [isMultiPiece, setIsMultiPiece] = useState(initialData?.is_multi_piece ?? false);
  const [pieces, setPieces] = useState<(ProductPieceInput & { id?: string })[]>(
    initialData?.pieces?.map((p) => ({
      id: p.id,
      name_en: p.name_en,
      name_ar: p.name_ar,
      sort_order: p.sort_order,
    })) || [],
  );
  const [colorSets, setColorSets] = useState<ProductColorSetInput[]>(() => {
    if (!initialData?.color_sets) return [];
    const pieceIdToIdx: Record<string, number> = {};
    for (const p of initialData.pieces || []) {
      pieceIdToIdx[p.id] = p.sort_order ?? 0;
    }
    return initialData.color_sets.map((cs) => ({
      sort_order: cs.sort_order,
      values: cs.values.map((v) => ({
        piece_id: pieceIdToIdx[v.piece_id]?.toString() ?? v.piece_id,
        color_option_id: v.color_option_id,
      })),
    }));
  });
  const { data: storeData } = useGetStoreQuery(storeId);
  const currencySymbol = storeData?.currency_symbol ?? "";

  const { data: allCategories = [] } = useGetCategoryTreeQuery({});

  const categoryPtMap = useMemo(() => {
    const map: Record<string, string> = {};
    const walk = (nodes: CategoryNode[]) => {
      for (const node of nodes) {
        if (node.product_type_id) map[node.id] = node.product_type_id;
        walk(node.children);
      }
    };
    walk(allCategories);
    return map;
  }, [allCategories]);

  const defaultValues: Record<string, string> = {};
  if (initialData) {
    defaultValues.name_en = initialData.name_en || "";
    defaultValues.name_ar = initialData.name_ar || "";
    defaultValues.brand = initialData.brand || "";
    defaultValues.category_id = initialData.category_id || "";
    defaultValues.source_url = initialData.source_url || "";
    defaultValues.collection = initialData.collection || "";
    defaultValues.collection_ar = initialData.collection_ar || "";
    defaultValues.short_description_en = initialData.short_description_en || "";
    defaultValues.short_description_ar = initialData.short_description_ar || "";
    defaultValues.long_description_en = initialData.long_description_en || "";
    defaultValues.long_description_ar = initialData.long_description_ar || "";
    defaultValues.price = initialData.price?.toString() || "";
    defaultValues.original_price = initialData.original_price?.toString() || "";
    defaultValues.quantity = initialData.quantity.toString();
    buildAttributeDefaults(initialData, defaultValues);
  } else {
    defaultValues.name_en = "";
    defaultValues.name_ar = "";
    defaultValues.brand = "";
    defaultValues.category_id = "";
    defaultValues.source_url = "";
    defaultValues.collection = "";
    defaultValues.collection_ar = "";
    defaultValues.short_description_en = "";
    defaultValues.short_description_ar = "";
    defaultValues.long_description_en = "";
    defaultValues.long_description_ar = "";
    defaultValues.price = "";
    defaultValues.original_price = "";
    defaultValues.quantity = "0";
  }

  const {
    control,
    handleSubmit,
    formState: { errors },
    trigger,
  } = useForm<Record<string, string>>({ defaultValues });

  const categoryId = useWatch({ control, name: "category_id" });
  const priceQuantity = useWatch({ control, name: ["price", "quantity"] });

  const effectiveProductTypeId = useMemo(() => {
    if (categoryId && categoryPtMap[categoryId]) return categoryPtMap[categoryId];
    return initialData?.product_type_id || "";
  }, [categoryId, categoryPtMap, initialData]);

  const formData = useProductFormData(effectiveProductTypeId);

  const attrFieldNames = useMemo(() => {
    return formData.allAttributes
      .filter(
        (attr) => attr.is_variant_defining && !(isMultiPiece && attr.code === "primary_color"),
      )
      .map((attr) => `attr_${attr.id}`);
  }, [formData.allAttributes, isMultiPiece]);

  const attrValues = useWatch({ control, name: attrFieldNames });

  const formValues = useMemo<Record<string, string>>(
    () => ({
      price: priceQuantity?.[0] ?? "",
      quantity: priceQuantity?.[1] ?? "",
    }),
    [priceQuantity],
  );

  const activeAttrGroups = useMemo(() => {
    return formData.attrGroups
      .filter((g) => g.id in formData.groupedAttributes)
      .toSorted((a, b) => a.sort_order - b.sort_order);
  }, [formData.attrGroups, formData.groupedAttributes]);

  const attrStepCount = useMemo(() => activeAttrGroups.length, [activeAttrGroups]);

  const lastAttrStep = ATTR_STEP_OFFSET + attrStepCount - 1;
  const VARIANTS_STEP = lastAttrStep + 1;
  const IMAGES_STEP = VARIANTS_STEP + 1;
  const REVIEW_STEP = IMAGES_STEP + 1;

  const allSteps = useMemo(() => {
    const steps: { step: number; key: string; label: string }[] = [
      { step: 0, key: "basicInfo", label: t("basicInfo") },
      { step: 1, key: "description", label: t("description") },
    ];
    for (const [i, g] of activeAttrGroups.entries()) {
      const label = localeValue(locale, g.name_ar, g.name_fa, g.name_en);
      steps.push({ step: ATTR_STEP_OFFSET + i, key: g.code, label });
    }
    steps.push(
      { step: VARIANTS_STEP, key: "priceInventory", label: t("priceInventory") },
      { step: IMAGES_STEP, key: "media", label: t("media") },
      { step: REVIEW_STEP, key: "review", label: t("review") },
    );
    return steps;
  }, [activeAttrGroups, locale, t, VARIANTS_STEP, IMAGES_STEP, REVIEW_STEP]);

  const colorOptions = useMemo(() => {
    const seen = new Set<string>();
    const options: {
      id: string;
      colorHex: string | null;
      label: string;
      colorFamily: string | null;
      isMajor: boolean;
      sortOrder: number;
    }[] = [];
    for (const attr of formData.allAttributes) {
      for (const opt of attr.options) {
        if (!opt.color_hex || seen.has(opt.id)) continue;
        seen.add(opt.id);
        options.push({
          id: opt.id,
          colorHex: opt.color_hex,
          label: localeValue(locale, opt.value_ar, opt.value_fa, opt.value_en),
          colorFamily: opt.color_family,
          isMajor: opt.is_major,
          sortOrder: opt.sort_order ?? 0,
        });
      }
    }
    return options.toSorted((a, b) => a.sortOrder - b.sortOrder);
  }, [formData.allAttributes, locale]);

  const currentAttrGroup = useMemo(() => {
    if (step < ATTR_STEP_OFFSET || step > lastAttrStep) return null;
    const attrStepIndex = step - ATTR_STEP_OFFSET;
    if (attrStepIndex >= activeAttrGroups.length) return null;
    return activeAttrGroups[attrStepIndex]!;
  }, [step, activeAttrGroups, lastAttrStep]);

  const currentGroupName = useMemo(() => {
    if (!currentAttrGroup) return "";
    return localeValue(
      locale,
      currentAttrGroup.name_ar,
      currentAttrGroup.name_fa,
      currentAttrGroup.name_en,
    );
  }, [currentAttrGroup, locale]);

  const currentAttrs = useMemo(() => {
    if (!currentAttrGroup) return [];
    if (isMultiPiece && currentAttrGroup.code === "colors-pattern") return [];
    return formData.groupedAttributes[currentAttrGroup.id] || [];
  }, [currentAttrGroup, formData.groupedAttributes, isMultiPiece]);

  const selectedOptionIds = useMemo(() => {
    const ids: Record<string, string[]> = {};
    let index = 0;
    for (const attr of formData.allAttributes) {
      if (!attr.is_variant_defining) continue;
      if (isMultiPiece && attr.code === "primary_color") continue;
      const val = attrValues?.[index];
      index += 1;
      if (!val) continue;
      if (attr.input_type === "multi-select") {
        try {
          ids[attr.id] = JSON.parse(val) as string[];
        } catch (error) {
          console.warn("Failed to parse multi-select attribute:", error);
          ids[attr.id] = [val];
        }
      } else {
        ids[attr.id] = [val];
      }
    }
    return ids;
  }, [formData.allAttributes, attrValues, isMultiPiece]);

  const validateColorSetsStep = (): boolean => {
    if (colorSets.length === 0) {
      toast.error(t("mustHaveAtLeastOnePiece"));
      return false;
    }
    const incomplete = colorSets.some((cs) => cs.values.some((v) => !v.color_option_id));
    if (incomplete) {
      toast.error("All pieces must have a color assigned in each color set");
      return false;
    }
    return true;
  };

  const validateMediaStep = (): boolean => {
    if (images.length < 3) {
      setMediaError(t("minImages", { count: 3 }));
      return false;
    }
    if (images.some((img) => !img.view_type_id || !img.alt_text_en.trim())) {
      setMediaError(t("fillImageDetails"));
      return false;
    }
    setMediaError(null);
    return true;
  };

  const validateVariantsStep = async (): Promise<boolean> => {
    if (!(await trigger("price"))) return false;
    setVariantError(null);
    if (variants.length > 0 && !variants.some((v) => v.is_active)) {
      setVariantError(t("atLeastOneActiveVariant"));
      return false;
    }
    if (variants.some((v) => v.is_active && !v.sku.trim())) {
      setVariantError(t("skuRequired"));
      return false;
    }
    return true;
  };

  const validateStep = async (): Promise<boolean> => {
    if (step === 0) {
      if (!effectiveProductTypeId) {
        toast.error(t("selectProductType"));
        return false;
      }
      return await trigger(["name_en", "category_id", "brand"]);
    }
    if (step === 1) return await trigger(["short_description_en", "short_description_ar"]);
    if (step === IMAGES_STEP) return validateMediaStep();
    if (step === ATTR_STEP_OFFSET && isMultiPiece) return validateColorSetsStep();
    if (step >= ATTR_STEP_OFFSET && step <= lastAttrStep)
      return await trigger(currentAttrs.map((a) => `attr_${a.id}`));
    if (step === VARIANTS_STEP) return await validateVariantsStep();
    return true;
  };

  const goNext = async () => {
    if (!(await validateStep())) return;
    setStep((s) => Math.min(s + 1, REVIEW_STEP));
  };
  const goBack = () => setStep((s) => Math.max(s - 1, 0));

  const variantSelectOptions = useMemo(() => {
    return variants.map((v) => {
      const optionLabels: string[] = [];
      let colorHex: string | undefined;
      for (const optId of v.attribute_option_ids) {
        for (const attr of formData.allAttributes) {
          const opt = attr.options?.find((o) => o.id === optId);
          if (opt) {
            const name = localeValue(locale, opt.value_ar, opt.value_fa, opt.value_en);
            optionLabels.push(name);
            if (opt.color_hex) colorHex = opt.color_hex;
          }
        }
      }
      return {
        signature: v.attribute_option_ids,
        sku: v.sku,
        label: `${v.sku} — ${optionLabels.join(" / ")}`,
        colorHex,
      };
    });
  }, [variants, formData.allAttributes, locale]);

  const colorSetIdxToId = useMemo(() => {
    if (!initialData?.color_sets) return;
    const map: Record<string, string> = {};
    for (const cs of initialData.color_sets) {
      map[cs.sort_order.toString()] = cs.id;
    }
    return map;
  }, [initialData]);

  const onSubmit = async (data: Record<string, string>) => {
    if (!effectiveProductTypeId) return;
    try {
      const payload = buildProductPayload(
        data,
        effectiveProductTypeId,
        variants,
        images,
        formData.allAttributes,
        isMultiPiece,
        pieces,
        colorSets,
        colorSetIdxToId,
      );

      let productId: string;
      if (isEdit && initialData) {
        const result = await formData
          .updateProduct({
            store_id: storeId,
            product_id: initialData.id,
            data: payload,
          })
          .unwrap();
        productId = result.id;
        toast.success(t("updated"));
      } else {
        const result = await formData.createProduct({ store_id: storeId, data: payload }).unwrap();
        productId = result.id;
        toast.success(t("created"));
      }

      if (onSuccess) onSuccess();
      else router.push(`/seller/stores/${storeId}/products/${productId}/generate-description`);
    } catch (error) {
      toast.error(extractApiError(error, t("error")));
    }
  };

  const saving = formData.creating || formData.updating;

  const isRtl = locale === "ar" || locale === "fa";
  const PrevIcon = isRtl ? FiChevronRight : FiChevronLeft;
  const NextIcon = isRtl ? FiChevronLeft : FiChevronRight;

  const windowStart = Math.max(0, Math.min(step - 1, allSteps.length - 3));
  const visibleSteps = allSteps.slice(windowStart, windowStart + 3);
  const showPrev = step > 0;
  const showNext = step < allSteps.length - 1;

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex min-h-0 flex-1 flex-col gap-6">
      {/* Steps indicator */}
      <div className="flex w-full items-center overflow-hidden rounded-full">
        {showPrev && (
          <button
            type="button"
            onClick={goBack}
            className={cn(
              "bg-muted text-muted-foreground hover:bg-muted/80 flex h-9 shrink-0 items-center justify-center px-3 py-1.5 text-sm transition-colors",
              isRtl ? "rounded-r-full" : "rounded-l-full",
            )}
          >
            <PrevIcon className="size-4" />
          </button>
        )}
        {visibleSteps.map((s, i) => {
          const isCurrent = s.step === step;
          const isPast = s.step < step;
          const isFirst = i === 0 && !showPrev;
          const isLast = i === visibleSteps.length - 1 && !showNext;
          return (
            <span
              key={s.step}
              className={cn(
                "flex h-9 flex-1 cursor-pointer items-center justify-center gap-1 px-3 py-1.5 text-sm whitespace-nowrap transition-colors",
                isCurrent && "bg-primary text-primary-foreground font-bold",
                !isCurrent && isPast && "bg-primary/10 text-primary",
                !isCurrent && !isPast && "bg-muted text-muted-foreground",
                isFirst && (isRtl ? "rounded-r-full" : "rounded-l-full"),
                isLast && (isRtl ? "rounded-l-full" : "rounded-r-full"),
              )}
            >
              {isPast ? (
                <FiCheckCircle className="size-3.5 shrink-0" />
              ) : (
                <span className="shrink-0">{s.step + 1}.</span>
              )}
              <span className="truncate">{s.label}</span>
            </span>
          );
        })}
        {showNext && (
          <button
            type="button"
            onClick={goNext}
            className={cn(
              "bg-muted text-muted-foreground hover:bg-muted/80 flex h-9 shrink-0 items-center justify-center px-3 py-1.5 text-sm transition-colors",
              isRtl ? "rounded-l-full" : "rounded-r-full",
            )}
          >
            <NextIcon className="size-4" />
          </button>
        )}
      </div>

      {/* Step content */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        {step === 0 && (
          <BasicInfoStep
            control={control}
            errors={errors}
            categoryTree={formData.categoryTree}
            brands={formData.brands}
            isMultiPiece={isMultiPiece}
            onMultiPieceChange={setIsMultiPiece}
            pieces={pieces}
            onPiecesChange={setPieces}
            isSourceUrlReadOnly={isEdit}
          />
        )}

        {step === 1 && <DescriptionStep control={control} errors={errors} />}

        {step >= ATTR_STEP_OFFSET && step <= lastAttrStep && (
          <>
            {isMultiPiece && step === ATTR_STEP_OFFSET ? (
              <CompositeColorSetsEditor
                pieces={pieces}
                colorSets={colorSets}
                onChange={setColorSets}
                colorOptions={colorOptions}
              />
            ) : (
              <AttributesStep
                currentAttrs={currentAttrs}
                groupName={currentGroupName}
                control={control}
              />
            )}
          </>
        )}

        {step === VARIANTS_STEP && (
          <PriceInventoryStep
            control={control}
            errors={errors}
            allAttributes={formData.allAttributes}
            selectedOptionIds={selectedOptionIds}
            optionsMap={formData.optionsMap}
            variants={variants}
            setVariants={setVariants}
            formValues={formValues}
            variantError={variantError}
            currencySymbol={currencySymbol}
            isMultiPiece={isMultiPiece}
            colorSets={colorSets}
          />
        )}

        {step === IMAGES_STEP && (
          <MediaStep
            images={images}
            viewTypes={formData.imageViewTypes}
            variants={variantSelectOptions}
            mediaError={mediaError}
            setImages={setImages}
          />
        )}

        {step === REVIEW_STEP && (
          <ReviewStep
            formValues={formValues}
            variants={variants}
            images={images}
            pieces={pieces}
            colorSets={colorSets}
          />
        )}
      </div>

      {/* Navigation buttons */}
      <div className="flex items-center gap-2 border-t pt-4">
        <div className="flex-1">
          {step > 0 && (
            <Button type="button" variant="outline" onClick={goBack} className="w-full">
              {t("previous")}
            </Button>
          )}
        </div>
        <div className="flex-1">
          {step < REVIEW_STEP ? (
            <Button type="button" onClick={goNext} className="w-full">
              {t("next")}
            </Button>
          ) : (
            <Button type="submit" disabled={saving} className="w-full">
              {saving ? t("saving") : t("submit")}
            </Button>
          )}
        </div>
      </div>
    </form>
  );
}
