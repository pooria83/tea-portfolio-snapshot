"use client";

import { type Control } from "react-hook-form";
import { useTranslations, useLocale } from "next-intl";
import { AttributeFieldRenderer } from "@/components/product/AttributeFieldRenderer";
import type { AttributeItem } from "@/types/api";

interface AttributesStepProps {
  currentAttrs: AttributeItem[];
  groupName: string;
  control: Control<Record<string, string>>;
}

export function AttributesStep({ currentAttrs, groupName, control }: AttributesStepProps) {
  const t = useTranslations("product");
  const locale = useLocale();

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">{groupName}</h2>
      {currentAttrs.length > 0 ? (
        <AttributeFieldRenderer attributes={currentAttrs} control={control} locale={locale} />
      ) : (
        <p className="text-muted-foreground text-sm">{t("noAttributes")}</p>
      )}
    </div>
  );
}
