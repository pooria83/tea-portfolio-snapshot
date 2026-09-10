"use client";

import { useState, useMemo } from "react";
import Image from "next/image";
import { useLocale, useTranslations } from "next-intl";
import { HiOutlinePhotograph, HiOutlineCube } from "react-icons/hi";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { localeValue } from "@/lib/locale";
import { safeHref } from "@/lib/url";
import { useGetStoreProductQuery, useGetProductTypeAttributesQuery } from "@/store/api/productApi";
import { ProductInfoPanel } from "@/components/product/ProductInfoPanel";
import type { ProductResponse } from "@/types/api";
import {
  ProductDetailSections,
  type AttributeMaps,
  type GroupedAttribute,
} from "@/components/product/ProductDetailSections";

interface ProductViewProps {
  storeId: string;
  productId: string;
  initialData?: ProductResponse;
}

export function ProductView({ storeId, productId, initialData }: ProductViewProps) {
  const locale = useLocale();
  const t = useTranslations("product");
  const {
    data: product = initialData,
    isLoading,
    error,
  } = useGetStoreProductQuery(
    {
      store_id: storeId,
      product_id: productId,
    },
    { skip: initialData != null },
  );

  const { data: attributes = [] } = useGetProductTypeAttributesQuery(
    { product_type_id: product?.product_type_id ?? "" },
    { skip: !product?.product_type_id },
  );

  const attributeMaps: AttributeMaps = useMemo(() => {
    const enAttr = new Map<string, string>();
    const arAttr = new Map<string, string>();
    const enOpt = new Map<string, string>();
    const arOpt = new Map<string, string>();
    for (const attr of attributes) {
      enAttr.set(attr.id, attr.name_en);
      arAttr.set(attr.id, attr.name_ar || "");
      for (const opt of attr.options) {
        enOpt.set(opt.id, opt.value_en);
        arOpt.set(opt.id, opt.value_ar || "");
      }
    }
    for (const av of product?.attribute_values ?? []) {
      const av2 = av as {
        attribute?: {
          name_ar?: string;
          name_en?: string;
          name_fa?: string;
          options?: Array<{ id: string; value_ar?: string; value_en?: string; value_fa?: string }>;
        };
      };
      const attrData = av2.attribute;
      if (attrData && attrData.name_en) {
        if (!enAttr.has(av.attribute_id)) {
          enAttr.set(av.attribute_id, attrData.name_en);
          arAttr.set(av.attribute_id, attrData.name_ar ?? "");
        }
        for (const opt of attrData.options ?? []) {
          if (opt.id && !enOpt.has(opt.id) && opt.value_en) {
            enOpt.set(opt.id, opt.value_en);
            arOpt.set(opt.id, opt.value_ar ?? "");
          }
        }
      }
    }
    return { enAttrMap: enAttr, arAttrMap: arAttr, enOptionMap: enOpt, arOptionMap: arOpt };
  }, [attributes, product?.attribute_values]);

  const groupedAttributes: GroupedAttribute[] = useMemo(() => {
    return (product?.attribute_values ?? []).reduce((acc, av) => {
      const existing = acc.find((e) => e.attribute_id === av.attribute_id);
      if (existing) {
        existing.values.push(av.value);
      } else {
        acc.push({ ...av, values: [av.value] });
      }
      return acc;
    }, [] as GroupedAttribute[]);
  }, [product?.attribute_values]);

  const [showInactiveVariants, setShowInactiveVariants] = useState(false);
  const [selectedColorId, setSelectedColorId] = useState<string | null>(null);

  const colorOptions = useMemo(() => {
    if (!product?.variants) return [];
    const seen = new Set<string>();
    return product.variants.reduce<
      Array<{ option: (typeof product.variants)[0]["attribute_options"][0]; variantIds: string[] }>
    >((acc, v) => {
      for (const opt of v.attribute_options || []) {
        if (opt.color_hex && !seen.has(opt.id)) {
          seen.add(opt.id);
          const variantIds = (product.variants ?? [])
            .filter((v2) => v2.attribute_options?.some((o) => o.id === opt.id))
            .map((v2) => v2.id);
          acc.push({ option: opt, variantIds });
        }
      }
      return acc;
    }, []);
  }, [product]);

  const activeColorId = selectedColorId ?? colorOptions[0]?.option.id ?? null;
  const selectedColor = colorOptions.find((c) => c.option.id === activeColorId);

  const filteredImages = useMemo(() => {
    const allImages = product?.images || [];
    const dedupe = (images: typeof allImages) => {
      const seen = new Set<string>();
      return images.filter((img) => {
        if (seen.has(img.image_url)) return false;
        seen.add(img.image_url);
        return true;
      });
    };
    if (!selectedColor || !activeColorId) return dedupe(allImages);
    const variantIds = new Set(selectedColor.variantIds);
    const matched = allImages.filter(
      (img) => img.variant_id != null && variantIds.has(img.variant_id),
    );
    if (matched.length > 0) return dedupe(matched);
    const unlinked = allImages.filter((img) => !img.variant_id);
    if (unlinked.length > 0) return dedupe(unlinked);
    return dedupe(allImages);
  }, [product?.images, selectedColor, activeColorId]);

  if (isLoading) return <ProductViewSkeleton />;
  if (error || !product) {
    return (
      <div className="flex flex-col items-center gap-4 rounded-xl border border-dashed p-12 text-center">
        <HiOutlineCube className="text-muted-foreground size-12" />
        <p className="text-muted-foreground">{t("productNotFound")}</p>
      </div>
    );
  }

  const name = product.name_en ?? "";
  const nameAr = product.name_ar ?? "";
  const shortDesc = product.short_description_en ?? "";
  const shortDescAr = product.short_description_ar ?? "";
  const longDesc = product.long_description_en ?? "";
  const longDescAr = product.long_description_ar ?? "";
  const hasSale =
    product.sale_price != null && product.original_price != null && product.original_price > 0;
  const displayPrice = hasSale ? product.sale_price! : product.price;
  const currency = product.currency || "SAR";

  const visibleVariants = showInactiveVariants
    ? product.variants
    : product.variants?.filter((v) => v.is_active);
  const totalVariants = product.variants?.length ?? 0;
  const activeVariants = product.variants?.filter((v) => v.is_active).length ?? 0;
  const inactiveCount = totalVariants - activeVariants;
  const sourceHref = safeHref(product.source_url);

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
      <div className="flex flex-col gap-6 lg:flex-row lg:gap-8">
        <div className="w-full lg:w-1/2">
          <ImageGallery
            images={filteredImages}
            name={name || "Product"}
            colorOptions={colorOptions}
            selectedColorId={activeColorId}
            onSelectColor={setSelectedColorId}
          />
        </div>

        <ProductInfoPanel
          product={product}
          name={name}
          nameAr={nameAr}
          shortDesc={shortDesc}
          shortDescAr={shortDescAr}
          displayPrice={displayPrice}
          currency={currency}
          hasSale={hasSale}
          sourceHref={sourceHref}
        />
      </div>

      <ProductDetailSections
        product={product}
        locale={locale}
        longDesc={longDesc}
        longDescAr={longDescAr}
        attributeMaps={attributeMaps}
        groupedAttributes={groupedAttributes}
        visibleVariants={visibleVariants}
        totalVariants={totalVariants}
        inactiveCount={inactiveCount}
        showInactiveVariants={showInactiveVariants}
        onToggleInactiveVariants={setShowInactiveVariants}
      />
    </div>
  );
}

function ImageGallery({
  images,
  name,
  colorOptions,
  selectedColorId,
  onSelectColor,
}: {
  images: {
    id: string;
    image_url: string;
    alt_text_en?: string | null;
    alt_text_ar?: string | null;
  }[];
  name: string;
  colorOptions: Array<{
    option: {
      id: string;
      color_hex?: string | null;
      value_en?: string;
      value_ar?: string;
      value_fa?: string;
    };
    variantIds: string[];
  }>;
  selectedColorId: string | null;
  onSelectColor: (id: string | null) => void;
}) {
  const locale = useLocale();
  const [selected, setSelected] = useState(0);

  if (images.length === 0) {
    return (
      <div className="bg-muted/30 flex aspect-square items-center justify-center rounded-xl border">
        <HiOutlinePhotograph className="text-muted-foreground/40 size-16" />
      </div>
    );
  }

  const current = images[selected];
  if (!current) return null;

  return (
    <div className="flex flex-col gap-3">
      <div className="bg-muted/10 relative aspect-square overflow-hidden rounded-xl border">
        <Image
          src={current.image_url}
          alt={current.alt_text_en || name}
          fill
          sizes="(max-width: 768px) 100vw, 50vw"
          className="object-contain"
          title={current.alt_text_ar || undefined}
        />
      </div>

      {colorOptions.length > 1 && (
        <div className="flex flex-wrap items-center gap-2">
          {colorOptions.map((c) => (
            <button
              key={c.option.id}
              type="button"
              onClick={() => {
                const next = c.option.id === selectedColorId ? null : c.option.id;
                onSelectColor(next);
                setSelected(0);
              }}
              className={cn(
                "flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
                c.option.id === selectedColorId
                  ? "border-ring bg-accent"
                  : "hover:border-muted-foreground/30 bg-muted/50 border-transparent",
              )}
            >
              {c.option.color_hex && (
                <span
                  className="inline-block size-3 shrink-0 rounded-full ring-1 ring-black/10"
                  style={{ backgroundColor: c.option.color_hex }}
                />
              )}
              {localeValue(
                locale,
                c.option.value_ar ?? "",
                c.option.value_fa ?? "",
                c.option.value_en ?? "",
              )}
            </button>
          ))}
        </div>
      )}

      {images.length > 1 && (
        <div className="flex gap-2 overflow-x-auto pb-1">
          {images.map((img, i) => (
            <button
              key={img.id}
              type="button"
              onClick={() => setSelected(i)}
              className={cn(
                "bg-muted/20 size-16 shrink-0 overflow-hidden rounded-lg border-2 transition-colors",
                i === selected
                  ? "border-ring"
                  : "hover:border-muted-foreground/30 border-transparent",
              )}
            >
              <Image
                src={img.image_url}
                alt={img.alt_text_en || `${name} ${i + 1}`}
                width={64}
                height={64}
                className="size-full object-cover"
              />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function ProductViewSkeleton() {
  return (
    <div className="mx-auto grid max-w-7xl gap-6 px-4 py-6 sm:px-6 lg:grid-cols-2 lg:px-8">
      <Skeleton className="aspect-square w-full rounded-xl" />
      <div className="space-y-4">
        <Skeleton className="h-8 w-3/4" />
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-10 w-1/3" />
        <div className="space-y-2">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-5/6" />
          <Skeleton className="h-4 w-2/3" />
        </div>
      </div>
    </div>
  );
}
