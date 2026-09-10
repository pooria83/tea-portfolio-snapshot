"use client";

import { useLocale } from "next-intl";
import { Controller, type Control } from "react-hook-form";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { ColorPicker, type ColorOption } from "@/components/ui/color-picker";
import { MultiSelect } from "@/components/ui/multi-select";
import { SingleSelect } from "@/components/ui/single-select";
import { CompositionInput } from "@/components/product/CompositionInput";
import { localeValue } from "@/lib/locale";
import type { AttributeItem, ValidationRule } from "@/types/api";

interface AttributeFieldRendererProps {
  attributes: AttributeItem[];
  control: Control;
  locale?: string;
}

type RuleHandler = (
  rule: ValidationRule,
  locale: string,
  rules: Record<string, unknown>,
  validators: Record<string, (v: string) => string | true>,
) => void;

const ruleHandlers: Record<string, RuleHandler> = {
  required: (rule, locale, rules) => {
    rules.required = localeValue(locale, rule.message.ar, rule.message.fa, rule.message.en);
  },
  min_length: (rule, locale, rules) => {
    rules.minLength = {
      value: rule.value,
      message: localeValue(locale, rule.message.ar, rule.message.fa, rule.message.en),
    };
  },
  max_length: (rule, locale, rules) => {
    rules.maxLength = {
      value: rule.value,
      message: localeValue(locale, rule.message.ar, rule.message.fa, rule.message.en),
    };
  },
  min: (rule, locale, rules) => {
    rules.min = {
      value: rule.value,
      message: localeValue(locale, rule.message.ar, rule.message.fa, rule.message.en),
    };
  },
  max: (rule, locale, rules) => {
    rules.max = {
      value: rule.value,
      message: localeValue(locale, rule.message.ar, rule.message.fa, rule.message.en),
    };
  },
  pattern: (rule, locale, _, validators) => {
    const patternVal = rule.value as string;
    const msg = localeValue(locale, rule.message.ar, rule.message.fa, rule.message.en);
    validators.pattern = (v: string) => (v.search(patternVal) === -1 ? msg : true);
  },
  min_select: (rule, locale, _, validators) => {
    const minVal = Number(rule.value ?? 1);
    const msg = localeValue(locale, rule.message.ar, rule.message.fa, rule.message.en);
    validators.minSelect = (v: string) => {
      let arr: string[];
      try {
        arr = v ? JSON.parse(v) : [];
      } catch (error) {
        console.warn("Failed to parse minSelect value:", error);
        arr = [];
      }
      return arr.length >= minVal ? true : msg;
    };
  },
  max_select: (rule, locale, _, validators) => {
    const maxVal = Number(rule.value ?? 99);
    const msg = localeValue(locale, rule.message.ar, rule.message.fa, rule.message.en);
    validators.maxSelect = (v: string) => {
      let arr: string[];
      try {
        arr = v ? JSON.parse(v) : [];
      } catch (error) {
        console.warn("Failed to parse maxSelect value:", error);
        arr = [];
      }
      return arr.length <= maxVal ? true : msg;
    };
  },
};

function buildRules(attr: AttributeItem, locale: string): Record<string, unknown> {
  const rules: Record<string, unknown> = {};
  if (!attr.validation_rules) return rules;

  const validators: Record<string, (v: string) => string | true> = {};

  for (const rule of attr.validation_rules) {
    ruleHandlers[rule.type]?.(rule, locale, rules, validators);
  }

  if (Object.keys(validators).length > 0) {
    rules.validate = validators;
  }
  return rules;
}

export function AttributeFieldRenderer({
  attributes,
  control,
  locale: propLocale,
}: AttributeFieldRendererProps) {
  const contextLocale = useLocale();
  const locale = propLocale || contextLocale;

  const tr = (attr: AttributeItem) => localeValue(locale, attr.name_ar, attr.name_fa, attr.name_en);

  return (
    <div className="space-y-4">
      {attributes.map((attr) => (
        <Controller
          key={attr.id}
          name={`attr_${attr.id}`}
          control={control}
          rules={buildRules(attr, locale)}
          render={({ field, fieldState }) => (
            <FormField
              label={tr(attr)}
              error={fieldState.error?.message}
              required={attr.is_required}
            >
              {attr.input_type === "text" && (
                <Input value={field.value || ""} onChange={field.onChange} placeholder={tr(attr)} />
              )}

              {attr.input_type === "textarea" && (
                <Textarea
                  value={field.value || ""}
                  onChange={field.onChange}
                  placeholder={tr(attr)}
                />
              )}

              {attr.input_type === "number" && (
                <Input
                  type="number"
                  value={field.value || ""}
                  onChange={(e) => field.onChange(e.target.value)}
                  placeholder={tr(attr)}
                />
              )}

              {attr.input_type === "switch" && (
                <Switch
                  checked={field.value === "true"}
                  onCheckedChange={(v) => field.onChange(v ? "true" : "false")}
                />
              )}

              {attr.input_type === "color-picker" && (
                <ColorPicker
                  options={attr.options.map((o): ColorOption => ({
                    id: o.id,
                    colorHex: o.color_hex,
                    label: localeValue(locale, o.value_ar, o.value_fa, o.value_en),
                    colorFamily: o.color_family,
                    isMajor: o.is_major,
                    sortOrder: o.sort_order ?? 0,
                  }))}
                  value={field.value}
                  onChange={field.onChange}
                />
              )}

              {attr.input_type === "composition" && (
                <CompositionInput
                  options={attr.options.map((opt) => ({
                    value: opt.id,
                    label: localeValue(locale, opt.value_ar, opt.value_fa, opt.value_en),
                  }))}
                  value={field.value || ""}
                  onChange={field.onChange}
                  placeholder={tr(attr)}
                />
              )}

              {attr.input_type === "select" && (
                <SingleSelect
                  options={attr.options.map((opt) => ({
                    value: opt.id,
                    label: localeValue(locale, opt.value_ar, opt.value_fa, opt.value_en),
                    colorHex: opt.color_hex ?? undefined,
                  }))}
                  value={field.value || ""}
                  onChange={field.onChange}
                  placeholder={tr(attr)}
                />
              )}

              {attr.input_type === "multi-select" && (
                <MultiSelect
                  options={attr.options.map((o) => ({
                    value: o.id,
                    label: localeValue(locale, o.value_ar, o.value_fa, o.value_en),
                    colorHex: o.color_hex ?? undefined,
                    colorFamily: o.color_family ?? undefined,
                  }))}
                  value={(() => {
                    if (!field.value) return [];
                    try {
                      const p = JSON.parse(field.value);
                      return Array.isArray(p) ? p : [p];
                    } catch (error) {
                      console.warn("Failed to parse multi-select field value:", error);
                      return [field.value];
                    }
                  })()}
                  onChange={(ids: string[]) =>
                    field.onChange(ids.length > 0 ? JSON.stringify(ids) : null)
                  }
                  placeholder={tr(attr)}
                />
              )}
            </FormField>
          )}
        />
      ))}
    </div>
  );
}
