"use client";

import { useTranslations } from "next-intl";
import type { ProductVariantInput, ProductPieceInput, ProductColorSetInput } from "@/types/api";
import type { ImageUploadItem } from "@/components/product/ProductImageUploader";

interface ReviewStepProps {
  formValues: Record<string, string>;
  variants: ProductVariantInput[];
  images: ImageUploadItem[];
  pieces?: ProductPieceInput[];
  colorSets?: ProductColorSetInput[];
}

export function ReviewStep({ formValues, variants, images, pieces, colorSets }: ReviewStepProps) {
  const t = useTranslations("product");

  const activePieces = pieces?.filter((p) => p.name_en?.trim()) || [];
  const activeColorSets = colorSets?.filter((cs) => cs.values.some((v) => v.color_option_id)) || [];

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">{t("review")}</h2>
      <div className="text-muted-foreground space-y-2 text-sm">
        <p>
          <strong>{t("price")}:</strong>{" "}
          {formValues?.price ? `${Number(formValues.price).toFixed(2)} SAR` : "-"}
        </p>
        <p>
          <strong>{t("quantity")}:</strong> {formValues?.quantity || "0"}
        </p>
        {variants.length > 0 && (
          <p>
            <strong>{t("variants")}:</strong> {variants.length} (
            {variants.filter((v) => v.is_active).length} active)
          </p>
        )}
        {activePieces.length > 0 && (
          <p>
            <strong>{t("pieces")}:</strong> {activePieces.length} piece(s)
          </p>
        )}
        {activeColorSets.length > 0 && (
          <p>
            <strong>{t("colorSets") || "Color Sets"}:</strong> {activeColorSets.length} set(s)
          </p>
        )}
        <p>
          <strong>{t("images")}:</strong> {images.length}
          {images.some((img) => img.variant_signature !== null) && (
            <span className="text-muted-foreground">
              {" "}
              ({images.filter((img) => img.variant_signature !== null).length} assigned to variants)
            </span>
          )}
        </p>
      </div>
    </div>
  );
}
