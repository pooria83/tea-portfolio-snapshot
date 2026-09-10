"use client";

import { useLocale } from "next-intl";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { localeValue } from "@/lib/locale";
import type { AttributeOptionItem, ProductColorSetResponse } from "@/types/api";

function colorCircleStyle(colorHex: string | null): React.CSSProperties {
  if (colorHex === "#FF00FF") {
    return {
      background:
        "conic-gradient(red, #ff8000, yellow, #80ff00, lime, #00ff80, aqua, #0080ff, blue, #8000ff, magenta, #ff0080, red)",
    };
  }
  return { backgroundColor: colorHex || "#ccc" };
}

interface VariantCardProps {
  variant: {
    id: string;
    sku: string;
    barcode?: string | null;
    price?: number | null;
    original_price?: number | null;
    quantity: number;
    is_active: boolean;
    attribute_options?: AttributeOptionItem[];
    color_set?: ProductColorSetResponse | null;
  };
  currencyCode?: string;
}

export function VariantCard({ variant, currencyCode = "SAR" }: VariantCardProps) {
  const locale = useLocale();

  return (
    <div
      className={cn(
        "rounded-xl border p-4 transition-colors",
        variant.is_active ? "bg-card" : "bg-muted/30 opacity-70",
      )}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="font-mono text-xs font-medium">{variant.sku}</span>
        <Badge variant={variant.is_active ? "default" : "secondary"} className="text-[10px]">
          {variant.is_active ? "Active" : "Inactive"}
        </Badge>
      </div>
      {variant.attribute_options && variant.attribute_options.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-1.5">
          {variant.attribute_options.map((opt) => (
            <span
              key={opt.id}
              className="bg-muted flex items-center gap-1.5 rounded px-1.5 py-0.5 text-[11px]"
            >
              {opt.color_hex && (
                <span
                  className="inline-block size-3 shrink-0 rounded-full ring-1 ring-black/10"
                  style={{ backgroundColor: opt.color_hex }}
                />
              )}
              {localeValue(locale, opt.value_ar, opt.value_fa, opt.value_en) || opt.id.slice(0, 6)}
            </span>
          ))}
        </div>
      )}
      {variant.color_set && variant.color_set.values.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-1.5">
          {variant.color_set.values.map((cv) => (
            <span
              key={cv.id}
              className="bg-muted flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px]"
            >
              <span
                className="inline-block size-3 shrink-0 rounded-full ring-1 ring-black/10"
                style={colorCircleStyle(cv.color_option?.color_hex ?? null)}
              />
              {cv.piece_name_en ?? ""}:{" "}
              {localeValue(
                locale,
                cv.color_option?.value_ar ?? "",
                cv.color_option?.value_fa ?? "",
                cv.color_option?.value_en ?? "",
              )}
            </span>
          ))}
        </div>
      )}
      <div className="flex items-baseline gap-1.5">
        {variant.price != null && (
          <>
            <span className="text-sm font-bold">
              {Number(variant.price).toLocaleString(undefined, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </span>
            <span className="text-muted-foreground text-[10px]">{currencyCode}</span>
          </>
        )}
        {variant.original_price != null && (
          <span className="text-muted-foreground text-[11px] line-through">
            {Number(variant.original_price).toLocaleString(undefined, {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
          </span>
        )}
      </div>
      <p className="text-muted-foreground mt-1 text-xs">Qty: {variant.quantity}</p>
      {variant.barcode && (
        <p className="text-muted-foreground mt-0.5 text-[10px]">Barcode: {variant.barcode}</p>
      )}
    </div>
  );
}
