"use client";

import { useState, useRef, useEffect, type ReactNode } from "react";
import { useTranslations } from "next-intl";
import ReactCrop, { type Crop, centerCrop, makeAspectCrop } from "react-image-crop";
import "react-image-crop/dist/ReactCrop.css";
import { HiOutlinePhotograph } from "react-icons/hi";
import { useUploadFileMutation } from "@/store/api/fileApi";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { ImageCropDialog } from "@/components/ui/image-crop-dialog";

interface PhotoUploaderProps {
  currentUrl?: string | undefined;
  onUploadComplete: (url: string) => void;
  fallback?: ReactNode | undefined;
  label?: string | undefined;
  maxSize?: number | undefined;
}

function centerAspectCrop(mediaWidth: number, mediaHeight: number): Crop {
  return centerCrop(
    makeAspectCrop({ unit: "%", width: 80 }, 1, mediaWidth, mediaHeight),
    mediaWidth,
    mediaHeight,
  );
}

export function PhotoUploader({
  currentUrl,
  onUploadComplete,
  fallback,
  label = "Upload",
  maxSize = 400,
}: PhotoUploaderProps) {
  const t = useTranslations("common");
  const [uploadFile, { isLoading: uploading }] = useUploadFileMutation();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [crop, setCrop] = useState<Crop>();
  const [completedCrop, setCompletedCrop] = useState<Crop>();
  const [imgSrc, setImgSrc] = useState<string>("");
  const [showCrop, setShowCrop] = useState(false);

  useEffect(() => {
    return () => {
      if (imgSrc) {
        URL.revokeObjectURL(imgSrc);
      }
    };
  }, [imgSrc]);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setSelectedFile(file);
    setImgSrc(URL.createObjectURL(file));
    setShowCrop(true);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleCropCancel = () => {
    setShowCrop(false);
    setSelectedFile(null);
    setImgSrc("");
    setCrop(undefined);
    setCompletedCrop(undefined);
  };

  const handleCropSave = async () => {
    if (!completedCrop || !imgRef.current || !selectedFile) return;

    const image = imgRef.current;
    const canvas = document.createElement("canvas");
    const cropX = (completedCrop.x / 100) * image.naturalWidth;
    const cropY = (completedCrop.y / 100) * image.naturalHeight;
    const cropWidth = (completedCrop.width / 100) * image.naturalWidth;
    const cropHeight = (completedCrop.height / 100) * image.naturalHeight;

    canvas.width = cropWidth;
    canvas.height = cropHeight;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.drawImage(image, cropX, cropY, cropWidth, cropHeight, 0, 0, cropWidth, cropHeight);

    canvas.toBlob(
      async (blob) => {
        if (!blob) return;
        const croppedFile = new File([blob], selectedFile.name.replace(/\.[^.]+$/, ".jpg"), {
          type: "image/jpeg",
        });

        try {
          const { url } = await uploadFile({ file: croppedFile, maxSize }).unwrap();
          onUploadComplete(url);
        } catch (error) {
          console.error("Failed to upload cropped avatar:", error);
        } finally {
          handleCropCancel();
        }
      },
      "image/jpeg",
      0.9,
    );
  };

  const onImageLoad = (e: React.SyntheticEvent<HTMLImageElement>) => {
    const { naturalWidth, naturalHeight } = e.currentTarget;
    setCrop(centerAspectCrop(naturalWidth, naturalHeight));
  };

  return (
    <>
      <div className="flex items-center gap-4">
        <Avatar size="lg">
          {currentUrl ? (
            <AvatarImage src={currentUrl} alt="Avatar" />
          ) : (
            <AvatarFallback>{fallback}</AvatarFallback>
          )}
        </Avatar>
        <div>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={handleFileSelect}
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={uploading}
            onClick={() => fileInputRef.current?.click()}
          >
            <HiOutlinePhotograph className="size-4" />
            {uploading ? "Uploading..." : label}
          </Button>
        </div>
      </div>

      {showCrop && selectedFile && crop && (
        <ImageCropDialog open>
          <h3 className="font-heading mb-4 text-base font-medium">{t("cropImage")}</h3>
          <div className="flex justify-center">
            <ReactCrop
              crop={crop}
              onChange={(_, c) => setCrop(c)}
              onComplete={(_, c) => setCompletedCrop(c)}
              aspect={1}
              circularCrop={!fallback}
              minWidth={50}
            >
              <img
                ref={imgRef}
                src={imgSrc}
                alt="Crop"
                onLoad={onImageLoad}
                className="max-h-[70vh] w-auto"
              />
            </ReactCrop>
          </div>
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="outline" onClick={handleCropCancel}>
              {t("cancel")}
            </Button>
            <Button onClick={handleCropSave} disabled={!completedCrop}>
              {t("save")}
            </Button>
          </div>
        </ImageCropDialog>
      )}
    </>
  );
}
