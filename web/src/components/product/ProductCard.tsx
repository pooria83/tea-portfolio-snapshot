"use client";

import { memo } from "react";
import Image from "next/image";
import { useRouter } from "@/i18n/routing";
import { useTranslations } from "next-intl";
import { HiOutlinePhotograph } from "react-icons/hi";
import { Eye, Pencil } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { localeValue } from "@/lib/locale";
import type { ProductListItem } from "@/types/api";

interface ProductCardProps {
  product: ProductListItem;
  storeId: string;
  locale: string;
  onView?: (() => void) | undefined;
  storeName?: string | null | undefined;
}

export const ProductCard = memo(function ProductCard({
  product,
  storeId,
  locale,
  onView,
  storeName,
}: ProductCardProps) {
  const router = useRouter();
  const t = useTranslations("product");
  const tCommon = useTranslations("common");
  const tDashboard = useTranslations("dashboard");
  const localizedName = localeValue(
    locale,
    product.name_ar ?? "",
    product.name_fa ?? "",
    product.name_en ?? "",
  );
  const firstImage = product.image_url;
  const hasSale = product.sale_price != null && product.original_price != null;
  const displayPrice = hasSale ? product.sale_price! : product.price;
  const displayCurrency = product.currency || "SAR";

  return (
    <div className="group block">
      <Card
        className={cn(
          "hover:border-ring/50 flex h-full flex-col overflow-hidden rounded-xl border pb-0 transition-colors",
        )}
      >
        {/* Image */}
        <div className="bg-muted/30 relative aspect-[4/3] w-full overflow-hidden">
          {firstImage ? (
            <Image
              src={firstImage}
              alt={localizedName}
              fill
              sizes="(max-width: 640px) 100vw, 25vw"
              className="object-contain transition-transform duration-300 group-hover:scale-105"
            />
          ) : (
            <div className="flex size-full items-center justify-center">
              <HiOutlinePhotograph className="text-muted-foreground/40 size-10" />
            </div>
          )}
          {hasSale && (
            <span className="bg-destructive text-destructive-foreground absolute top-2 left-2 rounded-md px-2 py-0.5 text-xs font-bold">
              -{Math.round((1 - product.sale_price! / product.original_price!) * 100)}%
            </span>
          )}
        </div>

        <CardContent className="flex flex-1 flex-col gap-1.5 p-3">
          {/* Name */}
          <p className="line-clamp-2 text-sm leading-snug font-medium">
            {localizedName || "\u00A0"}
          </p>

          {/* Brand + Status */}
          <div className="flex items-center gap-2">
            {product.brand_name && (
              <span className="text-muted-foreground truncate text-xs">{product.brand_name}</span>
            )}
            <Badge
              variant={product.status === "active" ? "default" : "secondary"}
              className="ml-auto shrink-0 text-[10px]"
            >
              {product.status}
            </Badge>
          </div>

          {/* Price */}
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
                <span className="text-muted-foreground text-[10px]">{displayCurrency}</span>
              </>
            )}
            {hasSale && (
              <span className="text-muted-foreground text-[11px] line-through">
                {Number(product.original_price!).toLocaleString(undefined, {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}
              </span>
            )}
          </div>

          {/* Store badge */}
          {storeName && (
            <div className="truncate text-[11px] font-medium text-sky-600 dark:text-sky-400">
              {storeName}
            </div>
          )}

          {/* Quantity */}
          <p className="text-muted-foreground text-[11px]">
            {t("quantity")}: {product.quantity}
            {product.has_variants && " · " + t("variants")}
          </p>
        </CardContent>

        {/* Actions — flush to card bottom and sides */}
        <div className="flex border-t">
          <Button
            type="button"
            variant="ghost"
            className="h-10 flex-1 rounded-none"
            onClick={onView}
          >
            <Eye className="size-4" />
            {tDashboard("viewDetails")}
          </Button>
          <div className="bg-border w-px" />
          <Button
            type="button"
            variant="ghost"
            className="h-10 flex-1 rounded-none"
            onClick={() => router.push(`/seller/stores/${storeId}/products/${product.id}/edit`)}
          >
            <Pencil className="size-4" />
            {tCommon("edit")}
          </Button>
        </div>
      </Card>
    </div>
  );
});
