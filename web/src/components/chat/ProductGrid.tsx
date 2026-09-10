"use client";

import { memo } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Sparkles } from "lucide-react";

import { RetryingThumbnail } from "@/components/chat/RetryingThumbnail";
import { localeValue } from "@/lib/locale";
import type { ChatProduct } from "@/types/api";

export const ChatProductCard = memo(function ChatProductCard({
  product,
  locale,
  onSelect,
  onFindSimilar,
}: {
  product: ChatProduct;
  locale: string;
  onSelect: (product: ChatProduct) => void;
  onFindSimilar?: (product: ChatProduct) => void;
}) {
  const t = useTranslations("admin.productSearch");
  const displayName =
    localeValue(locale, product.name_ar ?? "", product.name_fa ?? "", product.name_en ?? "") ||
    product.name ||
    "—";
  const displayBrand =
    localeValue(locale, product.brand_ar ?? "", product.brand_fa ?? "", product.brand_en ?? "") ||
    product.brand;
  return (
    <div className="relative h-full min-w-0">
      <button
        type="button"
        onClick={() => onSelect(product)}
        className="border-border bg-card text-card-foreground hover:bg-accent flex h-full w-full flex-col overflow-hidden rounded-xl border text-start transition-colors"
      >
        <div className="relative aspect-square w-full shrink-0">
          {product.image_url ? (
            <div className="bg-muted h-full w-full overflow-hidden">
              <RetryingThumbnail
                key={product.image_url}
                src={product.image_url}
                alt={displayName}
              />
            </div>
          ) : (
            <div className="bg-muted h-full w-full" aria-hidden />
          )}
        </div>
        <div className="flex min-h-0 flex-1 flex-col gap-0.5 p-3">
          <p className="line-clamp-2 text-sm font-medium">{displayName}</p>
          {displayBrand && <p className="text-muted-foreground truncate text-xs">{displayBrand}</p>}
          {product.price != null && (
            <p className="mt-auto text-sm font-semibold">
              {product.price} {product.currency}
            </p>
          )}
        </div>
      </button>
      {onFindSimilar && (
        <button
          type="button"
          aria-label={t("findSimilar")}
          title={t("findSimilar")}
          onClick={(event) => {
            event.stopPropagation();
            onFindSimilar(product);
          }}
          className="bg-background/85 hover:bg-background text-foreground absolute top-2 left-2 rounded-full p-1.5 shadow transition-colors"
        >
          <Sparkles className="size-4" />
        </button>
      )}
    </div>
  );
});

export const ProductGrid = memo(function ProductGrid({
  products,
  onSelect,
  onFindSimilar,
  locale,
}: {
  products: ChatProduct[];
  onSelect: (product: ChatProduct) => void;
  onFindSimilar?: (product: ChatProduct) => void;
  locale?: string;
}) {
  const uiLocale = useLocale();
  const effectiveLocale = locale || uiLocale;
  return (
    <div className="grid auto-rows-fr grid-cols-2 gap-3 md:grid-cols-4">
      {products.map((product) => (
        <ChatProductCard
          key={product.id}
          product={product}
          locale={effectiveLocale}
          onSelect={onSelect}
          {...(onFindSimilar ? { onFindSimilar } : {})}
        />
      ))}
    </div>
  );
});
