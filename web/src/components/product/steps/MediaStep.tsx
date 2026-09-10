"use client";

import { useTranslations, useLocale } from "next-intl";
import {
  ProductImageUploader,
  type ImageUploadItem,
  type VariantSelectOption,
} from "@/components/product/ProductImageUploader";
import type { ImageViewTypeItem } from "@/types/api";

interface MediaStepProps {
  images: ImageUploadItem[];
  viewTypes: ImageViewTypeItem[];
  variants: VariantSelectOption[];
  mediaError: string | null;
  setImages: (images: ImageUploadItem[]) => void;
}

export function MediaStep({ images, viewTypes, variants, mediaError, setImages }: MediaStepProps) {
  const t = useTranslations("product");
  const locale = useLocale();

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">{t("media")}</h2>
      <ProductImageUploader
        images={images}
        viewTypes={viewTypes}
        variants={variants}
        locale={locale}
        onChange={setImages}
      />
      {mediaError && <p className="text-destructive text-sm">{mediaError}</p>}
    </div>
  );
}
