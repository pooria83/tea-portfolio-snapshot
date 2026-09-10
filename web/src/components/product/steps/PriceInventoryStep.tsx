"use client";

import { Controller, type Control, type FieldErrors } from "react-hook-form";
import { useTranslations, useLocale } from "next-intl";
import { HiOutlineCube } from "react-icons/hi";
import { FormField } from "@/components/ui/form-field";
import { InputGroup, InputGroupAddon, InputGroupInput } from "@/components/ui/input-group";
import { VariantGridEditor } from "@/components/product/VariantGridEditor";
import type {
  AttributeItem,
  AttributeOptionItem,
  ProductVariantInput,
  ProductColorSetInput,
} from "@/types/api";

interface PriceInventoryStepProps {
  control: Control<Record<string, string>>;
  errors: FieldErrors<Record<string, string>>;
  allAttributes: AttributeItem[];
  selectedOptionIds: Record<string, string[]>;
  optionsMap: Record<string, AttributeOptionItem[]>;
  variants: ProductVariantInput[];
  setVariants: (v: ProductVariantInput[]) => void;
  formValues: Record<string, string>;
  variantError: string | null;
  currencySymbol: string;
  isMultiPiece?: boolean;
  colorSets?: ProductColorSetInput[];
}

export function PriceInventoryStep({
  control,
  errors,
  allAttributes,
  selectedOptionIds,
  optionsMap,
  variants,
  setVariants,
  formValues,
  variantError,
  currencySymbol,
  isMultiPiece,
  colorSets = [],
}: PriceInventoryStepProps) {
  const t = useTranslations("product");
  const locale = useLocale();

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">{t("priceInventory")}</h2>

      <div className="space-y-3">
        <FormField label={t("price")} error={errors.price?.message}>
          <Controller
            name="price"
            control={control}
            rules={{
              required: t("required"),
              validate: (v) => (!Number.isNaN(Number(v)) && Number(v) > 0) || t("invalidPrice"),
            }}
            render={({ field }) => (
              <InputGroup>
                <InputGroupAddon className="text-xs font-medium">{currencySymbol}</InputGroupAddon>
                <InputGroupInput
                  type="number"
                  step="0.01"
                  {...field}
                  placeholder={t("pricePlaceholder")}
                />
              </InputGroup>
            )}
          />
        </FormField>
        <FormField label={t("originalPrice")} error={errors.original_price?.message}>
          <Controller
            name="original_price"
            control={control}
            rules={{
              validate: (v) =>
                !v || (!Number.isNaN(Number(v)) && Number(v) >= 0) || t("invalidPrice"),
            }}
            render={({ field }) => (
              <InputGroup>
                <InputGroupAddon className="text-xs font-medium">{currencySymbol}</InputGroupAddon>
                <InputGroupInput
                  type="number"
                  step="0.01"
                  {...field}
                  placeholder={t("originalPricePlaceholder")}
                />
              </InputGroup>
            )}
          />
        </FormField>
        <FormField label={t("quantity")} error={errors.quantity?.message}>
          <Controller
            name="quantity"
            control={control}
            rules={{
              validate: (v) =>
                (!Number.isNaN(Number(v)) && Number(v) >= 0 && Number.isInteger(Number(v))) ||
                t("invalidQuantity"),
            }}
            render={({ field }) => (
              <InputGroup>
                <InputGroupAddon>
                  <HiOutlineCube className="size-4" />
                </InputGroupAddon>
                <InputGroupInput type="number" {...field} placeholder={t("quantityPlaceholder")} />
              </InputGroup>
            )}
          />
        </FormField>
      </div>

      <div className="space-y-3">
        <h3 className="text-base font-medium">{t("variants")}</h3>
        {variantError && <p className="text-destructive text-sm">{variantError}</p>}
        <VariantGridEditor
          attributes={allAttributes}
          selectedOptionIds={selectedOptionIds}
          optionsMap={optionsMap}
          variants={variants}
          onChange={setVariants}
          defaultQuantity={formValues?.quantity ? Number(formValues.quantity) : 0}
          locale={locale}
          currencySymbol={currencySymbol}
          isMultiPiece={isMultiPiece}
          colorSets={colorSets}
        />
      </div>
    </div>
  );
}
