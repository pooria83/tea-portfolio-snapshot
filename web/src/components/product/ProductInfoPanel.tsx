"use client";

import { useTranslations } from "next-intl";
import { FiExternalLink } from "react-icons/fi";
import { HiOutlineCalendar } from "react-icons/hi";

import { Badge } from "@/components/ui/badge";
import type { ProductResponse } from "@/types/product";

interface ProductInfoPanelProps {
  product: ProductResponse;
  name: string;
  nameAr: string;
  shortDesc: string;
  shortDescAr: string;
  displayPrice: number | null;
  currency: string;
  hasSale: boolean;
  sourceHref: string | null;
}

export function ProductInfoPanel({
  product,
  name,
  nameAr,
  shortDesc,
  shortDescAr,
  displayPrice,
  currency,
  hasSale,
  sourceHref,
}: ProductInfoPanelProps) {
  const t = useTranslations("product");

  return (
    <div className="flex w-full flex-col gap-4 lg:w-1/2">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={product.status === "active" ? "default" : "secondary"} className="text-xs">
          {product.status}
        </Badge>
        <span className="text-muted-foreground flex items-center gap-1 text-xs">
          <HiOutlineCalendar className="size-3" />
          {new Date(product.created_at).toLocaleDateString()}
        </span>
      </div>

      <h1 className="text-2xl leading-tight font-bold lg:text-3xl">{name}</h1>
      {nameAr && (
        <h2 className="text-muted-foreground text-xl leading-tight font-medium" dir="rtl">
          {nameAr}
        </h2>
      )}

      {product.brand_name && (
        <p className="text-muted-foreground text-sm font-medium">{product.brand_name}</p>
      )}

      {sourceHref && (
        <a
          href={sourceHref}
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary inline-flex items-center gap-1.5 text-sm font-medium hover:underline"
        >
          <FiExternalLink className="size-4" />
          {t("openSourceLink")}
        </a>
      )}

      <div className="flex items-baseline gap-2">
        {displayPrice == null ? (
          <span className="text-muted-foreground">{t("priceNotSet")}</span>
        ) : (
          <>
            <span className="text-3xl font-bold">
              {Number(displayPrice).toLocaleString(undefined, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </span>
            <span className="text-muted-foreground text-sm">{currency}</span>
          </>
        )}
        {hasSale && (
          <>
            <span className="text-muted-foreground text-lg line-through">
              {Number(product.original_price!).toLocaleString(undefined, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </span>
            <Badge variant="destructive" className="text-xs">
              -{Math.round((1 - product.sale_price! / product.original_price!) * 100)}%
            </Badge>
          </>
        )}
      </div>

      <p className="text-muted-foreground text-sm">
        <span className="font-medium">{t("stock")}:</span> {product.quantity}
        {product.has_variants && ` ${t("managedViaVariants")}`}
      </p>

      {shortDesc && (
        <p className="text-muted-foreground border-t pt-3 text-sm leading-relaxed">{shortDesc}</p>
      )}
      {shortDescAr && (
        <p className="text-muted-foreground text-sm leading-relaxed" dir="rtl">
          {shortDescAr}
        </p>
      )}

      <div className="border-t pt-3">
        <MetaRow label={t("collection")} value={product.collection} />
        {product.collection_ar && (
          <MetaRow label={t("collectionAr")} value={product.collection_ar} />
        )}
        <MetaRow label={t("hasVariants")} value={product.has_variants ? t("yes") : t("no")} />
        {product.is_multi_piece && (
          <MetaRow
            label={t("pieces")}
            value={
              product.pieces
                ?.map((p) => p.name_en)
                .filter(Boolean)
                .join(", ") || t("yes")
            }
          />
        )}
      </div>
    </div>
  );
}

export function MetaRow({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <p className="text-muted-foreground text-sm">
      <span className="font-medium">{label}:</span> {value}
    </p>
  );
}
