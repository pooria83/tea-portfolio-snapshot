"use client";

import { useLocale } from "next-intl";

import { RetryingThumbnail } from "@/components/chat/RetryingThumbnail";
import { localeValue } from "@/lib/locale";
import type { ProductListItem } from "@/types/api";

interface HomeProductCardProps {
  product: ProductListItem;
  onSelect: (product: ProductListItem) => void;
}

export function HomeProductCard({ product, onSelect }: HomeProductCardProps) {
  const locale = useLocale();
  const localizedName = localeValue(
    locale,
    product.name_ar ?? "",
    product.name_fa ?? "",
    product.name_en ?? "",
  );
  const firstImage = product.image_url;
  const hasSale = product.sale_price != null && product.original_price != null;
  const displayPrice = hasSale ? product.sale_price! : product.price;

  return (
    <button
      type="button"
      onClick={() => onSelect(product)}
      className="border-border bg-card text-card-foreground hover:border-ring/50 group flex h-full w-full flex-col overflow-hidden rounded-xl border text-start transition-colors"
    >
      <div className="bg-muted/30 relative aspect-[4/3] w-full overflow-hidden">
        {firstImage ? (
          <div className="bg-muted h-full w-full overflow-hidden">
            <RetryingThumbnail src={firstImage} alt={localizedName} />
          </div>
        ) : (
          <div className="bg-muted h-full w-full" aria-hidden />
        )}
        {hasSale && product.original_price != null && product.sale_price != null && (
          <span className="bg-destructive text-destructive-foreground absolute top-2 left-2 rounded-md px-2 py-0.5 text-xs font-bold">
            -{Math.round((1 - product.sale_price / product.original_price) * 100)}%
          </span>
        )}
      </div>
      <div className="flex min-h-0 flex-1 flex-col gap-1 p-3">
        <p className="line-clamp-2 text-sm leading-snug font-medium">{localizedName || "\u00A0"}</p>
        {product.brand_name && (
          <p className="text-muted-foreground truncate text-xs">{product.brand_name}</p>
        )}
        <div className="mt-auto flex items-baseline gap-1.5">
          {displayPrice == null ? (
            <span className="text-muted-foreground text-xs">—</span>
          ) : (
            <>
              <span className="text-sm font-bold">
                {Number(displayPrice).toLocaleString(undefined, {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}
              </span>
              <span className="text-muted-foreground text-[10px]">{product.currency}</span>
            </>
          )}
          {hasSale && product.original_price != null && (
            <span className="text-muted-foreground text-[11px] line-through">
              {Number(product.original_price).toLocaleString(undefined, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </span>
          )}
        </div>
      </div>
    </button>
  );
}
