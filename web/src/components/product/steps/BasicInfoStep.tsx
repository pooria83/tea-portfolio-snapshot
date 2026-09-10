"use client";

import { useMemo } from "react";
import { Controller, type Control, type FieldErrors } from "react-hook-form";
import { useTranslations } from "next-intl";
import { localeValue } from "@/lib/locale";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { SingleSelect, type SingleSelectOption } from "@/components/ui/single-select";
import { FiPlus, FiTrash2 } from "react-icons/fi";
import { isSafeHref } from "@/lib/url";
import type { BrandItem, CategoryNode, ProductPieceInput } from "@/types/api";

interface BasicInfoStepProps {
  control: Control<Record<string, string>>;
  errors: FieldErrors<Record<string, string>>;
  categoryTree: CategoryNode[];
  brands: BrandItem[];
  isMultiPiece?: boolean;
  onMultiPieceChange?: (value: boolean) => void;
  pieces?: ProductPieceInput[];
  onPiecesChange?: (pieces: ProductPieceInput[]) => void;
  isSourceUrlReadOnly?: boolean;
}

function toTreeOptions(nodes: CategoryNode[]): SingleSelectOption[] {
  return nodes.map((node) => ({
    value: node.id,
    label: localeValue("en", node.name_ar, node.name_fa, node.name_en),
    icon: node.icon ?? undefined,
    children: node.children && node.children.length > 0 ? toTreeOptions(node.children) : undefined,
  }));
}

export function BasicInfoStep({
  control,
  errors,
  categoryTree,
  brands,
  isMultiPiece = false,
  onMultiPieceChange,
  pieces = [],
  onPiecesChange,
  isSourceUrlReadOnly = false,
}: BasicInfoStepProps) {
  const t = useTranslations("product");

  const categoryOptions: SingleSelectOption[] = useMemo(
    () => toTreeOptions(categoryTree),
    [categoryTree],
  );

  const brandOptions: SingleSelectOption[] = useMemo(
    () =>
      brands.map((b) => {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";
        const logoUrl =
          b.logo_url && apiUrl ? `${new URL(apiUrl).origin}${b.logo_url}` : b.logo_url || undefined;
        return {
          value: b.id,
          label: b.name_en,
          imageUrl: logoUrl || undefined,
          dir: "ltr" as const,
        };
      }),
    [brands],
  );

  const updatePiece = (index: number, field: keyof ProductPieceInput, value: unknown) => {
    const next = pieces.map((p, i) => (i === index ? { ...p, [field]: value } : p));
    onPiecesChange?.(next);
  };

  const removePiece = (index: number) => {
    const next = pieces.filter((_, i) => i !== index);
    onPiecesChange?.(next);
  };

  const addPiece = () => {
    onPiecesChange?.([...pieces, { name_en: "", sort_order: pieces.length }]);
  };

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">{t("basicInfo")}</h2>
      <FormField label={t("nameEn")} required error={errors.name_en?.message}>
        <Controller
          name="name_en"
          control={control}
          rules={{ required: t("required") }}
          render={({ field }) => <Input {...field} placeholder={t("namePlaceholder")} />}
        />
      </FormField>
      <FormField label={t("nameAr")} error={errors.name_ar?.message}>
        <Controller
          name="name_ar"
          control={control}
          render={({ field }) => (
            <Input {...field} placeholder={t("nameArPlaceholder")} dir="rtl" />
          )}
        />
      </FormField>
      <FormField label={t("brand")} required error={errors.brand?.message}>
        <Controller
          name="brand"
          control={control}
          rules={{ required: t("required") }}
          render={({ field }) => (
            <SingleSelect
              options={brandOptions}
              value={field.value || ""}
              onChange={field.onChange}
              placeholder={t("brandPlaceholder")}
            />
          )}
        />
      </FormField>
      <FormField label={t("category")} required error={errors.category_id?.message}>
        <Controller
          name="category_id"
          control={control}
          rules={{ required: t("required") }}
          render={({ field }) => (
            <SingleSelect
              options={categoryOptions}
              value={field.value || ""}
              onChange={field.onChange}
              placeholder={t("categoryPlaceholder")}
            />
          )}
        />
      </FormField>
      <FormField label={t("sourceLink")}>
        <Controller
          name="source_url"
          control={control}
          rules={{
            validate: (value) => {
              if (!value || isSafeHref(value)) return true;
              return t("invalidUrl");
            },
          }}
          render={({ field }) => (
            <Input
              {...field}
              value={field.value || ""}
              placeholder="https://..."
              readOnly={isSourceUrlReadOnly}
              className={isSourceUrlReadOnly ? "text-muted-foreground cursor-default" : ""}
            />
          )}
        />
      </FormField>
      <FormField label={t("collection")}>
        <Controller
          name="collection"
          control={control}
          render={({ field }) => <Input {...field} placeholder={t("collectionPlaceholder")} />}
        />
      </FormField>
      <FormField label={t("collectionAr")}>
        <Controller
          name="collection_ar"
          control={control}
          render={({ field }) => (
            <Input {...field} placeholder={t("collectionArPlaceholder")} dir="rtl" />
          )}
        />
      </FormField>

      {/* Multi-Piece Toggle & Piece Name Editor */}
      <div className="border-t pt-4">
        <div className="flex items-center justify-between gap-4">
          <div className="space-y-0.5">
            <label className="text-sm font-medium">{t("multiPiece")}</label>
            <p className="text-muted-foreground text-xs">{t("multiPieceDesc")}</p>
          </div>
          <Switch checked={isMultiPiece} onCheckedChange={(v) => onMultiPieceChange?.(v)} />
        </div>

        {isMultiPiece && (
          <div className="mt-4 space-y-3">
            {pieces.map((piece, i) => (
              <div key={i} className="flex items-start gap-3 rounded-lg border p-3">
                <div className="flex-1">
                  <FormField label={t("pieceName")}>
                    <Input
                      value={piece.name_en || ""}
                      onChange={(e) => updatePiece(i, "name_en", e.target.value)}
                      placeholder={t("pieceNamePlaceholder")}
                    />
                  </FormField>
                </div>
                <button
                  type="button"
                  onClick={() => removePiece(i)}
                  className="text-destructive hover:bg-destructive/10 mt-6 flex size-8 shrink-0 items-center justify-center rounded-md transition-colors"
                >
                  <FiTrash2 className="size-4" />
                </button>
              </div>
            ))}
            <Button type="button" variant="outline" size="sm" onClick={addPiece} className="gap-1">
              <FiPlus className="size-4" />
              {t("addPiece")}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
