"use client";

import { Controller, type Control, type FieldErrors } from "react-hook-form";
import { useTranslations } from "next-intl";
import { FiFileText } from "react-icons/fi";
import { FormField } from "@/components/ui/form-field";
import { InputGroup, InputGroupAddon, InputGroupTextarea } from "@/components/ui/input-group";

interface DescriptionStepProps {
  control: Control<Record<string, string>>;
  errors: FieldErrors<Record<string, string>>;
}

export function DescriptionStep({ control, errors }: DescriptionStepProps) {
  const t = useTranslations("product");

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">{t("description")}</h2>
      <FormField label={t("shortDescriptionEn")} error={errors.short_description_en?.message}>
        <Controller
          name="short_description_en"
          control={control}
          rules={{
            required: t("required"),
            minLength: { value: 20, message: t("shortDescriptionMinLength") },
          }}
          render={({ field }) => (
            <InputGroup>
              <InputGroupAddon align="inline-start">
                <FiFileText className="size-4" />
              </InputGroupAddon>
              <InputGroupTextarea
                {...field}
                placeholder={t("shortDescriptionPlaceholder")}
                rows={3}
              />
            </InputGroup>
          )}
        />
      </FormField>
      <FormField label={t("shortDescriptionAr")}>
        <Controller
          name="short_description_ar"
          control={control}
          render={({ field }) => (
            <InputGroup>
              <InputGroupAddon align="inline-start">
                <FiFileText className="size-4" />
              </InputGroupAddon>
              <InputGroupTextarea
                {...field}
                placeholder={t("shortDescriptionArPlaceholder")}
                rows={3}
                dir="rtl"
              />
            </InputGroup>
          )}
        />
      </FormField>
      <FormField label={t("longDescriptionEn")}>
        <Controller
          name="long_description_en"
          control={control}
          render={({ field }) => (
            <InputGroup>
              <InputGroupAddon align="inline-start">
                <FiFileText className="size-4" />
              </InputGroupAddon>
              <InputGroupTextarea
                {...field}
                placeholder={t("longDescriptionPlaceholder")}
                rows={6}
              />
            </InputGroup>
          )}
        />
      </FormField>
      <FormField label={t("longDescriptionAr")}>
        <Controller
          name="long_description_ar"
          control={control}
          render={({ field }) => (
            <InputGroup>
              <InputGroupAddon align="inline-start">
                <FiFileText className="size-4" />
              </InputGroupAddon>
              <InputGroupTextarea
                {...field}
                placeholder={t("longDescriptionArPlaceholder")}
                rows={6}
                dir="rtl"
              />
            </InputGroup>
          )}
        />
      </FormField>
    </div>
  );
}
