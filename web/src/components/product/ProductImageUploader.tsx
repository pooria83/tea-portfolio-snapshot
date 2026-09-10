"use client";

import { useState, useRef, useEffect } from "react";
import { useTranslations } from "next-intl";
import { HiOutlinePhotograph, HiOutlineTrash } from "react-icons/hi";
import { FiCrop } from "react-icons/fi";
import ReactCrop, { type Crop } from "react-image-crop";
import "react-image-crop/dist/ReactCrop.css";
import { useUploadFileMutation } from "@/store/api/fileApi";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ImageCropDialog } from "@/components/ui/image-crop-dialog";
import { localeValue } from "@/lib/locale";
import type { ImageViewTypeItem } from "@/types/api";
import { SingleSelect } from "@/components/ui/single-select";

function canvasToBlob(
  canvas: HTMLCanvasElement,
  type: string,
  quality: number,
): Promise<Blob | null> {
  return new Promise((resolve) => canvas.toBlob((blob) => resolve(blob), type, quality));
}

async function cropImageFromSource(
  source: HTMLImageElement | ImageBitmap,
  crop: Crop,
): Promise<Blob | null> {
  const nw = "naturalWidth" in source ? source.naturalWidth : source.width;
  const nh = "naturalHeight" in source ? source.naturalHeight : source.height;
  const cropX = (crop.x / 100) * nw;
  const cropY = (crop.y / 100) * nh;
  const cropWidth = (crop.width / 100) * nw;
  const cropHeight = (crop.height / 100) * nh;

  const canvas = document.createElement("canvas");
  canvas.width = cropWidth;
  canvas.height = cropHeight;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.drawImage(source, cropX, cropY, cropWidth, cropHeight, 0, 0, cropWidth, cropHeight);
  return canvasToBlob(canvas, "image/jpeg", 0.9);
}

async function getCroppableSource(
  imgElement: HTMLImageElement,
  fallbackUrl: string,
): Promise<HTMLImageElement | ImageBitmap> {
  const testCanvas = document.createElement("canvas");
  const ctx = testCanvas.getContext("2d")!;
  ctx.drawImage(imgElement, 0, 0);
  try {
    ctx.getImageData(0, 0, 1, 1);
    return imgElement;
  } catch {
    const resp = await fetch(fallbackUrl);
    const blob = await resp.blob();
    return createImageBitmap(blob);
  }
}

export interface VariantSelectOption {
  signature: string[];
  sku: string;
  label: string;
  colorHex?: string | undefined;
}

export interface ImageUploadItem {
  id: string;
  file?: File | undefined;
  image_url: string;
  view_type_id: string | null;
  variant_signature: string[] | null;
  alt_text_ar: string;
  alt_text_en: string;
  alt_text_fa: string;
  sort_order: number;
  uploading?: boolean | undefined;
  error?: string | undefined;
}

interface ProductImageUploaderProps {
  images: ImageUploadItem[];
  viewTypes: ImageViewTypeItem[];
  variants: VariantSelectOption[];
  locale: string;
  onChange: (images: ImageUploadItem[]) => void;
}

export function ProductImageUploader({
  images,
  viewTypes,
  variants,
  locale,
  onChange,
}: ProductImageUploaderProps) {
  const t = useTranslations("product");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadFile] = useUploadFileMutation();
  const imagesRef = useRef(images);
  useEffect(() => {
    imagesRef.current = images;
  }, [images]);
  const [cropImageId, setCropImageId] = useState<string | null>(null);
  const [crop, setCrop] = useState<Crop>();
  const [completedCrop, setCompletedCrop] = useState<Crop>();
  const imgRef = useRef<HTMLImageElement>(null);

  const handleFilesSelected = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;

    const currentImages = imagesRef.current;
    const newImages: ImageUploadItem[] = files.map((file, i) => ({
      id: `new_${Date.now()}_${i}`,
      file,
      image_url: URL.createObjectURL(file),
      view_type_id: null,
      variant_signature: null,
      alt_text_ar: "",
      alt_text_en: "",
      alt_text_fa: "",
      sort_order: currentImages.length + i,
      uploading: true,
    }));

    onChange([...currentImages, ...newImages]);

    for (const img of newImages) {
      try {
        const result = await uploadFile({
          file: img.file!,
        }).unwrap();
        onChange(
          imagesRef.current.map((p: ImageUploadItem) => {
            if (p.id !== img.id) return p;
            if (p.image_url.startsWith("blob:")) {
              URL.revokeObjectURL(p.image_url);
            }
            const { ...item } = p;
            return { ...item, image_url: result.url, uploading: false };
          }),
        );
      } catch {
        onChange(
          imagesRef.current.map((p: ImageUploadItem) =>
            p.id === img.id ? { ...p, uploading: false, error: "Upload failed" } : p,
          ),
        );
      }
    }

    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleRemove = (id: string) => {
    const target = imagesRef.current.find((img) => img.id === id);
    if (target?.image_url.startsWith("blob:")) {
      URL.revokeObjectURL(target.image_url);
    }
    onChange(imagesRef.current.filter((img) => img.id !== id));
  };

  const handleViewTypeChange = (id: string, view_type_id: string) => {
    onChange(imagesRef.current.map((img) => (img.id === id ? { ...img, view_type_id } : img)));
  };

  const handleVariantChange = (id: string, signatureJson: string) => {
    onChange(
      imagesRef.current.map((img) =>
        img.id === id
          ? {
              ...img,
              variant_signature: signatureJson
                ? (() => {
                    try {
                      return JSON.parse(signatureJson);
                    } catch {
                      return null;
                    }
                  })()
                : null,
            }
          : img,
      ),
    );
  };

  const handleAltTextChange = (id: string, field: string, value: string) => {
    onChange(imagesRef.current.map((img) => (img.id === id ? { ...img, [field]: value } : img)));
  };

  const openCrop = (id: string) => {
    setCropImageId(id);
    setCrop(undefined);
    setCompletedCrop(undefined);
  };

  const closeCrop = () => {
    setCropImageId(null);
    setCrop(undefined);
    setCompletedCrop(undefined);
  };

  const handleCropSave = async () => {
    if (!completedCrop || !imgRef.current || !cropImageId) return;

    const currentTarget = imagesRef.current.find((i) => i.id === cropImageId);
    if (!currentTarget) return;

    try {
      const source = await getCroppableSource(imgRef.current, currentTarget.image_url);
      const blob = await cropImageFromSource(source, completedCrop);
      if (!blob) {
        closeCrop();
        return;
      }

      const croppedFile = new File([blob], "cropped.jpg", { type: "image/jpeg" });
      const result = await uploadFile({ file: croppedFile }).unwrap();
      onChange(
        imagesRef.current.map((p) => {
          if (p.id !== cropImageId) return p;
          if (p.image_url.startsWith("blob:")) {
            URL.revokeObjectURL(p.image_url);
          }
          return { ...p, image_url: result.url };
        }),
      );
    } catch (error) {
      console.error("Failed to upload cropped image:", error);
    }
    closeCrop();
  };

  const handleCropImageLoad = (e: React.SyntheticEvent<HTMLImageElement>) => {
    const { naturalWidth, naturalHeight } = e.currentTarget;
    const newCrop: Crop = {
      unit: "%",
      width: 80,
      height: 80,
      x: 10,
      y: 10,
    };
    if (naturalWidth > naturalHeight) {
      newCrop.width = (naturalHeight / naturalWidth) * 80;
      newCrop.x = (100 - newCrop.width) / 2;
    } else {
      newCrop.height = (naturalWidth / naturalHeight) * 80;
      newCrop.y = (100 - newCrop.height) / 2;
    }
    setCrop(newCrop);
  };

  const cropTarget = images.find((i) => i.id === cropImageId);

  return (
    <div className="space-y-4">
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        multiple
        className="hidden"
        onChange={handleFilesSelected}
      />
      <Button type="button" variant="outline" onClick={() => fileInputRef.current?.click()}>
        <HiOutlinePhotograph className="size-4" />
        {t("uploadImages")}
      </Button>

      {images.length === 0 && <p className="text-muted-foreground text-sm">{t("noImages")}</p>}

      <div className="space-y-3">
        {images.map((img) => (
          <div
            key={img.id}
            className="border-border flex flex-col items-start gap-4 rounded-lg border p-3 sm:flex-row"
          >
            <div className="relative size-24 shrink-0 overflow-hidden rounded-md max-sm:h-48 max-sm:w-full">
              {img.uploading && (
                <div className="bg-background/80 absolute inset-0 z-10 flex items-center justify-center">
                  <span className="text-muted-foreground text-xs">{t("uploading")}</span>
                </div>
              )}
              <img src={img.image_url} alt="" className="h-full w-full object-cover" />
              <div className="absolute top-1 right-1 z-10 flex gap-1">
                <button
                  type="button"
                  onClick={() => openCrop(img.id)}
                  className="bg-background/80 hover:bg-background rounded p-1.5"
                  title={t("crop")}
                >
                  <FiCrop className="size-4" />
                </button>
                <button
                  type="button"
                  onClick={() => handleRemove(img.id)}
                  className="bg-destructive/80 hover:bg-destructive rounded p-1.5 text-white"
                  title={t("remove")}
                >
                  <HiOutlineTrash className="size-4" />
                </button>
              </div>
            </div>

            <div className="flex flex-1 flex-col gap-2 max-sm:w-full">
              <SingleSelect
                options={viewTypes.map((vt) => ({
                  value: vt.id,
                  label: localeValue(locale, vt.name_ar, vt.name_fa, vt.name_en),
                }))}
                value={img.view_type_id || ""}
                onChange={(v) => handleViewTypeChange(img.id, v)}
                placeholder={t("selectViewType")}
                size="sm"
                triggerClassName="h-8 text-xs"
              />
              {variants.length > 0 && (
                <SingleSelect
                  options={[
                    { value: "", label: t("general") },
                    ...Array.from(
                      new Map(variants.map((v) => [JSON.stringify(v.signature), v])).values(),
                    ).map((v) => ({
                      value: JSON.stringify(v.signature),
                      label: v.label,
                      colorHex: v.colorHex,
                    })),
                  ]}
                  value={img.variant_signature ? JSON.stringify(img.variant_signature) : ""}
                  onChange={(v) => handleVariantChange(img.id, v)}
                  placeholder={t("general")}
                  size="sm"
                  triggerClassName="h-8 text-xs"
                />
              )}
              <Input
                placeholder={t("altPlaceholder")}
                value={img.alt_text_en}
                onChange={(e) => handleAltTextChange(img.id, "alt_text_en", e.target.value)}
                className="h-8 text-xs"
                dir="ltr"
              />
              <Input
                placeholder={t("altPlaceholderAr")}
                value={img.alt_text_ar}
                onChange={(e) => handleAltTextChange(img.id, "alt_text_ar", e.target.value)}
                className="h-8 text-xs"
                dir="rtl"
              />
            </div>

            {img.error && <p className="text-destructive text-xs">{img.error}</p>}
          </div>
        ))}
      </div>

      {cropTarget && crop && (
        <ImageCropDialog open>
          <h3 className="font-heading mb-4 text-base font-medium">{t("cropImage")}</h3>
          <div className="flex justify-center">
            <ReactCrop
              crop={crop}
              onChange={(_, c) => setCrop(c)}
              onComplete={(_, c) => setCompletedCrop(c)}
            >
              <img
                ref={imgRef}
                src={cropTarget.image_url}
                alt="Crop"
                crossOrigin="anonymous"
                onLoad={handleCropImageLoad}
                className="max-h-[70vh] w-auto"
              />
            </ReactCrop>
          </div>
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="outline" onClick={closeCrop}>
              {t("cancel")}
            </Button>
            <Button onClick={handleCropSave} disabled={!completedCrop}>
              {t("save")}
            </Button>
          </div>
        </ImageCropDialog>
      )}
    </div>
  );
}
