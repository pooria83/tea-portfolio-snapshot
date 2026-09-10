"use client";

import { memo, useState } from "react";
import { useTranslations, useLocale } from "next-intl";
import { FiChevronRight, FiChevronLeft, FiChevronDown, FiChevronUp } from "react-icons/fi";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import { PageLayout } from "@/components/layout/PageLayout";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  useGetProductTypesQuery,
  useGetCategoryTreeQuery,
  useGetProductTypeAttributesQuery,
} from "@/store/api/productApi";
import { localeValue } from "@/lib/locale";
import type { CategoryNode, AttributeItem, AttributeOptionItem } from "@/types/api";

function isLeaf(node: CategoryNode): boolean {
  return node.children.length === 0;
}

const inputTypeStyles: Record<string, string> = {
  select: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
  "multi-select": "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300",
  color: "bg-pink-100 text-pink-800 dark:bg-pink-900/30 dark:text-pink-300",
  number: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300",
  text: "bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-300",
  composition: "bg-teal-100 text-teal-800 dark:bg-teal-900/30 dark:text-teal-300",
};

const inputTypeLabels: Record<string, string> = {
  select: "Select",
  "multi-select": "Multi",
  color: "Color",
  number: "Number",
  text: "Text",
  composition: "Composition",
};

function TranslationTooltip({
  children,
  ar,
  fa,
  en,
}: {
  children: React.ReactNode;
  ar: string;
  fa: string;
  en: string;
}) {
  return (
    <Tooltip>
      <TooltipTrigger className="inline">{children}</TooltipTrigger>
      <TooltipContent side="top" align="center" sideOffset={4}>
        <div className="space-y-0.5 text-xs">
          <div>
            <span className="font-semibold">EN:</span> {en || "—"}
          </div>
          <div>
            <span className="font-semibold">AR:</span> {ar || "—"}
          </div>
          <div>
            <span className="font-semibold">FA:</span> {fa || "—"}
          </div>
        </div>
      </TooltipContent>
    </Tooltip>
  );
}

const OptionChip = memo(function OptionChip({
  opt,
  locale,
}: {
  opt: AttributeOptionItem;
  locale: string;
}) {
  const label = localeValue(locale, opt.value_ar, opt.value_fa, opt.value_en);
  return (
    <TranslationTooltip ar={opt.value_ar} fa={opt.value_fa} en={opt.value_en}>
      <span
        className="bg-secondary inline-flex cursor-default items-center gap-1 rounded-full border px-2.5 py-1 text-sm"
        title={opt.code ?? label}
      >
        {opt.color_hex && (
          <span
            className="inline-block size-3 rounded-full border"
            style={{ backgroundColor: opt.color_hex }}
          />
        )}
        {label}
      </span>
    </TranslationTooltip>
  );
});

const SHOW_MORE_THRESHOLD = 15;

const AttributeRow = memo(function AttributeRow({
  attr,
  locale,
  t,
}: {
  attr: AttributeItem;
  locale: string;
  t: (key: string, params?: Record<string, string | number | Date>) => string;
}) {
  const name = localeValue(locale, attr.name_ar, attr.name_fa, attr.name_en);
  const [showAll, setShowAll] = useState(false);
  const hasMany = attr.options.length > SHOW_MORE_THRESHOLD;
  const visibleOptions =
    hasMany && !showAll ? attr.options.slice(0, SHOW_MORE_THRESHOLD) : attr.options;
  return (
    <div className="border-border space-y-1 border-s-2 py-1.5 ps-3">
      <div className="flex items-center gap-2">
        <TranslationTooltip ar={attr.name_ar} fa={attr.name_fa} en={attr.name_en}>
          <span className="text-sm font-bold">{name}</span>
        </TranslationTooltip>
        <span
          className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
            inputTypeStyles[attr.input_type] ?? "bg-gray-100 text-gray-800"
          }`}
        >
          {inputTypeLabels[attr.input_type] ?? attr.input_type}
        </span>
        {attr.is_variant_defining && (
          <span className="rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-600 dark:bg-amber-900/20 dark:text-amber-400">
            variant
          </span>
        )}
        {attr.is_search_affecting && (
          <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-600 dark:bg-emerald-900/20 dark:text-emerald-400">
            search affecting
          </span>
        )}
      </div>
      {attr.options.length > 0 && (
        <div>
          <div className="flex flex-wrap gap-1.5">
            {visibleOptions.map((opt) => (
              <OptionChip key={opt.id} opt={opt} locale={locale} />
            ))}
          </div>
          {hasMany && (
            <button
              type="button"
              className="text-muted-foreground hover:text-foreground border-border hover:bg-muted/50 mt-1.5 inline-flex cursor-pointer items-center gap-1 rounded-md border px-2 py-1 text-xs"
              onClick={() => setShowAll((v) => !v)}
            >
              {showAll ? (
                <FiChevronUp className="size-3.5" />
              ) : (
                <FiChevronDown className="size-3.5" />
              )}
              {showAll
                ? t("showLess")
                : t("showMore", { count: attr.options.length - SHOW_MORE_THRESHOLD })}
            </button>
          )}
        </div>
      )}
    </div>
  );
});

const TreeNode = memo(function TreeNode({
  node,
  depth,
  attributes,
  locale,
  t,
}: {
  node: CategoryNode;
  depth: number;
  attributes: AttributeItem[];
  locale: string;
  t: (key: string, params?: Record<string, string | number | Date>) => string;
}) {
  const [expanded, setExpanded] = useState(depth < 1);
  const [showAttributes, setShowAttributes] = useState(false);
  const leaf = isLeaf(node);
  const name = localeValue(locale, node.name_ar, node.name_fa, node.name_en);
  const open = leaf ? showAttributes : expanded;
  const rtl = locale === "ar" || locale === "fa";
  let ChevronIcon = FiChevronRight;
  if (open) {
    ChevronIcon = FiChevronDown;
  } else if (rtl) {
    ChevronIcon = FiChevronLeft;
  }

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        className="hover:bg-muted/50 flex w-full cursor-pointer items-center gap-1.5 rounded px-2 py-1.5 text-start"
        style={{ paddingInlineStart: `${depth * 24 + 8}px` }}
        onClick={() => {
          if (leaf) {
            setShowAttributes((v) => !v);
          } else {
            setExpanded((v) => !v);
          }
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            if (leaf) {
              setShowAttributes((v) => !v);
            } else {
              setExpanded((v) => !v);
            }
          }
        }}
      >
        <span className="text-muted-foreground flex size-4 shrink-0 items-center justify-center">
          <ChevronIcon className="size-3.5" />
        </span>
        <span
          className={`truncate text-sm font-medium ${leaf ? "text-foreground" : "text-foreground/90"}`}
        >
          {leaf ? (
            <span className="flex items-center gap-1.5">
              <span className="bg-muted-foreground/40 size-1.5 shrink-0 rounded-full" />
              <TranslationTooltip ar={node.name_ar} fa={node.name_fa} en={node.name_en}>
                <span>{name}</span>
              </TranslationTooltip>
            </span>
          ) : (
            <TranslationTooltip ar={node.name_ar} fa={node.name_fa} en={node.name_en}>
              <span>{name}</span>
            </TranslationTooltip>
          )}
        </span>
        <span className="text-muted-foreground ms-auto shrink-0 text-[11px]">
          {leaf ? `${attributes.length} attributes` : `${node.children.length} subcategories`}
        </span>
      </div>

      {!leaf &&
        expanded &&
        node.children.map((child) => (
          <TreeNode
            key={child.id}
            node={child}
            depth={depth + 1}
            attributes={attributes}
            locale={locale}
            t={t}
          />
        ))}

      {leaf && showAttributes && (
        <div className="space-y-1 py-1" style={{ paddingInlineStart: `${(depth + 1) * 24 + 8}px` }}>
          {attributes.length === 0 ? (
            <p className="text-muted-foreground px-3 py-1 text-xs italic">No attributes</p>
          ) : (
            attributes.map((attr) => (
              <AttributeRow key={attr.id} attr={attr} locale={locale} t={t} />
            ))
          )}
        </div>
      )}
    </div>
  );
});

function TreeSkeleton() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 6 }).map((_, i) => (
        <div
          key={i}
          className="flex items-center gap-2"
          style={{ paddingInlineStart: `${(i % 3) * 24}px` }}
        >
          <Skeleton className="size-4 rounded" />
          <Skeleton className="h-4 max-w-[200px] flex-1" />
          <Skeleton className="h-3 w-20" />
        </div>
      ))}
    </div>
  );
}

export default function CategoryAttributeTree() {
  const t = useTranslations("catalog");
  const commonT = useTranslations("common");
  const locale = useLocale();

  const {
    data: productTypes = [],
    isLoading: typesLoading,
    isError: typesError,
  } = useGetProductTypesQuery();

  const [selectedTypeId, setSelectedTypeId] = useState<string | undefined>();
  const typeId = selectedTypeId ?? productTypes[0]?.id;

  const {
    data: categories = [],
    isLoading: catLoading,
    isError: catError,
  } = useGetCategoryTreeQuery(
    { ...(typeId ? { product_type_id: typeId } : {}) },
    { skip: !typeId },
  );

  const {
    data: attributes = [],
    isLoading: attrLoading,
    isError: attrError,
  } = useGetProductTypeAttributesQuery({ product_type_id: typeId! }, { skip: !typeId });

  const loading = typesLoading || (typeId != null && (catLoading || attrLoading));
  const error = typesError || catError || attrError;

  return (
    <PageLayout>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{t("title")}</h1>
        <Select
          value={typeId ?? ""}
          onValueChange={(val) => setSelectedTypeId(val ?? undefined)}
          disabled={typesLoading || productTypes.length === 0}
        >
          <SelectTrigger className="w-64">
            <SelectValue placeholder={t("selectProductType")}>
              {typeId
                ? localeValue(
                    locale,
                    productTypes.find((p) => p.id === typeId)?.name_ar ?? "",
                    productTypes.find((p) => p.id === typeId)?.name_fa ?? "",
                    productTypes.find((p) => p.id === typeId)?.name_en ?? "",
                  )
                : t("selectProductType")}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            {productTypes.map((pt) => (
              <SelectItem key={pt.id} value={pt.id}>
                <TranslationTooltip ar={pt.name_ar} fa={pt.name_fa} en={pt.name_en}>
                  <span>{localeValue(locale, pt.name_ar, pt.name_fa, pt.name_en)}</span>
                </TranslationTooltip>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {loading && <TreeSkeleton />}

      {!loading && error && (
        <div className="flex flex-col items-center gap-4 rounded-lg border border-dashed p-12 text-center">
          <p className="text-muted-foreground">{commonT("error")}</p>
        </div>
      )}

      {!loading && !error && productTypes.length === 0 && (
        <div className="flex flex-col items-center gap-4 rounded-lg border border-dashed p-12 text-center">
          <p className="text-muted-foreground">{t("noProductTypes")}</p>
        </div>
      )}

      {!loading && !error && productTypes.length > 0 && categories.length === 0 && (
        <div className="flex flex-col items-center gap-4 rounded-lg border border-dashed p-12 text-center">
          <p className="text-muted-foreground">{t("noCategories")}</p>
        </div>
      )}

      {!loading && !error && categories.length > 0 && (
        <div className="bg-card rounded-lg border">
          {categories.map((cat) => (
            <TreeNode
              key={cat.id}
              node={cat}
              depth={0}
              attributes={attributes}
              locale={locale}
              t={t}
            />
          ))}
        </div>
      )}
    </PageLayout>
  );
}
