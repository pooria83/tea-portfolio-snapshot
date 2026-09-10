"use client";

import { useState, useEffect, useRef, useMemo } from "react";
import Image from "next/image";
import {
  Search,
  ChevronDown,
  ArrowLeft,
  Check,
  ChevronRight,
  ChevronLeft,
  Eraser,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { IconRenderer } from "@/lib/icons";

export interface SingleSelectOption {
  value: string;
  label: string;
  colorHex?: string | undefined;
  imageUrl?: string | undefined;
  icon?: string | undefined;
  children?: SingleSelectOption[] | undefined;
  dir?: "ltr" | "rtl" | "auto" | undefined;
}

interface SingleSelectProps {
  options: SingleSelectOption[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string | undefined;
  selectLabel?: string;
  cancelLabel?: string;
  searchPlaceholder?: string;
  emptyMessage?: string;
  searchThreshold?: number;
  className?: string;
  triggerClassName?: string;
  contentClassName?: string;
  optionClassName?: string;
  size?: "sm" | "default";
  disabled?: boolean;
}

function flattenTree(
  options: SingleSelectOption[],
  prefix = "",
): {
  value: string;
  label: string;
  imageUrl?: string;
  colorHex?: string;
  icon?: string;
  path: string;
}[] {
  const result: {
    value: string;
    label: string;
    imageUrl?: string;
    colorHex?: string;
    icon?: string;
    path: string;
  }[] = [];
  for (const opt of options) {
    if (opt.children && opt.children.length > 0) {
      const label = prefix ? `${prefix} > ${opt.label}` : opt.label;
      result.push(...flattenTree(opt.children, label));
    } else {
      const item: (typeof result)[number] = {
        value: opt.value,
        label: opt.label,
        path: prefix,
      };
      if (opt.imageUrl !== undefined) item.imageUrl = opt.imageUrl;
      if (opt.colorHex !== undefined) item.colorHex = opt.colorHex;
      if (opt.icon !== undefined) item.icon = opt.icon;
      result.push(item);
    }
  }
  return result;
}

function findOptionByValue(
  options: SingleSelectOption[],
  targetValue: string,
): SingleSelectOption | undefined {
  for (const opt of options) {
    if (opt.value === targetValue) return opt;
    if (opt.children) {
      const found = findOptionByValue(opt.children, targetValue);
      if (found) return found;
    }
  }
  return undefined;
}

function colorCircleStyle(colorHex?: string): React.CSSProperties {
  if (colorHex === "#FF00FF") {
    return {
      background:
        "conic-gradient(red, #ff8000, yellow, #80ff00, lime, #00ff80, aqua, #0080ff, blue, #8000ff, magenta, #ff0080, red)",
    };
  }
  return { backgroundColor: colorHex || "#ccc" };
}

export function SingleSelect({
  options,
  value,
  onChange,
  placeholder = "Select...",
  selectLabel = "Select",
  cancelLabel = "Back",
  searchPlaceholder = "Search...",
  emptyMessage = "No options",
  searchThreshold = 10,
  className,
  triggerClassName,
  contentClassName,
  optionClassName,
  size = "default",
  disabled = false,
}: SingleSelectProps) {
  const locale = useLocale();
  const isRtl = locale === "ar" || locale === "fa";
  const tCommon = useTranslations("common");
  const resolvedCancel = cancelLabel === "Back" ? tCommon("back") : cancelLabel;
  const resolvedSelect = selectLabel === "Select" ? tCommon("select") : selectLabel;
  const resolvedSearch =
    searchPlaceholder === "Search..." ? tCommon("searchOptions") : searchPlaceholder;
  const resolvedEmpty = emptyMessage === "No options" ? tCommon("noOptions") : emptyMessage;
  const [isOpen, setIsOpen] = useState(false);
  const [tempValue, setTempValue] = useState(value);
  const [searchQuery, setSearchQuery] = useState("");
  const [navStack, setNavStack] = useState<SingleSelectOption[]>([]);
  const searchRef = useRef<HTMLInputElement>(null);
  const isTree = useMemo(() => options.some((o) => o.children && o.children.length > 0), [options]);

  useEffect(() => {
    if (isOpen) {
      setTempValue(value);
      setSearchQuery("");
      setNavStack([]);
    }
  }, [isOpen, value]);

  useEffect(() => {
    if (isOpen && options.length > searchThreshold) {
      searchRef.current?.focus();
    }
  }, [isOpen, options.length, searchThreshold]);

  const showSearch = isTree || options.length > searchThreshold;

  const flattenedTree = useMemo(() => (isTree ? flattenTree(options) : null), [options, isTree]);

  const currentOptions = useMemo(() => {
    if (searchQuery) {
      if (isTree) {
        return (flattenedTree ?? []).filter((o) =>
          o.label.toLowerCase().includes(searchQuery.toLowerCase()),
        );
      }
      return options.filter((o) => o.label.toLowerCase().includes(searchQuery.toLowerCase()));
    }

    if (navStack.length === 0) return options;
    const current = navStack.at(-1);
    return current?.children || options;
  }, [options, isTree, searchQuery, navStack, flattenedTree]);

  const triggerLabel = useMemo(() => {
    if (!value) return null;
    const opt = findOptionByValue(options, value);
    return opt || null;
  }, [options, value]);

  const handleOptionClick = (option: SingleSelectOption) => {
    if (option.children && option.children.length > 0 && !searchQuery) {
      setNavStack((prev) => [...prev, option]);
      return;
    }
    setTempValue((prev) => (prev === option.value ? "" : option.value));
  };

  const handleBreadcrumbClick = (index: number) => {
    setNavStack((prev) => prev.slice(0, index));
  };

  const handleSelect = () => {
    if (tempValue) {
      onChange(tempValue);
    }
    setIsOpen(false);
  };

  const handleCancel = () => {
    setIsOpen(false);
  };

  const heightClass = size === "sm" ? "h-7 text-xs" : "h-9 text-sm";

  return (
    <>
      {/* Trigger */}
      <div
        className={cn(
          "border-input dark:bg-input/30 flex w-full items-center gap-0 rounded-lg border bg-transparent shadow-xs transition-colors",
          "focus-within:border-ring focus-within:ring-ring/50 focus-within:ring-[3px]",
          "hover:bg-accent hover:text-accent-foreground dark:hover:bg-input/50",
          "disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50",
          heightClass,
          !value && "text-muted-foreground",
          triggerClassName,
          className,
        )}
      >
        <button
          type="button"
          disabled={disabled}
          onClick={() => setIsOpen(true)}
          className={cn(
            "flex flex-1 items-center gap-2 px-2.5 py-1",
            isRtl ? "text-right" : "text-left",
          )}
        >
          {triggerLabel ? (
            <>
              {triggerLabel.colorHex && (
                <span
                  className="inline-block size-4 shrink-0 rounded-full border"
                  style={colorCircleStyle(triggerLabel.colorHex)}
                />
              )}
              {triggerLabel.icon && (
                <IconRenderer code={triggerLabel.icon} className="size-5 shrink-0" />
              )}
              <span className="flex-1 truncate" dir={triggerLabel.dir}>
                {triggerLabel.label}
              </span>
              {triggerLabel.imageUrl && (
                <Image
                  src={triggerLabel.imageUrl}
                  alt=""
                  width={24}
                  height={24}
                  className="size-6 shrink-0 rounded object-contain dark:bg-white dark:p-0.5"
                />
              )}
            </>
          ) : (
            <span className="flex-1">{placeholder}</span>
          )}
          {value && (
            <span
              role="button"
              tabIndex={-1}
              onClick={(e) => {
                e.stopPropagation();
                onChange("");
              }}
              className="hover:text-destructive flex shrink-0 items-center transition-colors"
              aria-label="Clear selection"
            >
              <Eraser className="size-3.5" />
            </span>
          )}
        </button>

        <ChevronDown className="pointer-events-none mr-2 size-4 shrink-0 opacity-50" />
      </div>

      {/* Dialog */}
      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogContent
          showCloseButton={false}
          className={cn(
            "flex flex-col gap-0 p-0",
            "fixed inset-0 max-h-none max-w-none translate-x-0 translate-y-0 rounded-none",
            "sm:top-1/2 sm:left-1/2 sm:max-h-[80dvh] sm:max-w-lg sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-xl",
            contentClassName,
          )}
        >
          {/* Header */}
          <DialogHeader className="shrink-0 border-b px-4 py-3">
            {/* Breadcrumb (tree mode) */}
            {isTree && navStack.length > 0 && (
              <div className="text-muted-foreground mb-2 flex items-center gap-1 text-xs">
                <button
                  type="button"
                  onClick={() => setNavStack([])}
                  className="hover:text-foreground transition-colors"
                >
                  {placeholder}
                </button>
                {navStack.map((crumb, i) => (
                  <span key={crumb.value} className="inline-flex items-center gap-1">
                    {isRtl ? (
                      <ChevronLeft className="size-3" />
                    ) : (
                      <ChevronRight className="size-3" />
                    )}
                    <button
                      type="button"
                      onClick={() => handleBreadcrumbClick(i + 1)}
                      className={cn(
                        "hover:text-foreground transition-colors",
                        i === navStack.length - 1 && "text-foreground font-medium",
                      )}
                    >
                      {crumb.label}
                    </button>
                  </span>
                ))}
              </div>
            )}

            <div className="flex items-center justify-between">
              <DialogTitle className="text-base">
                {isTree && navStack.length > 0
                  ? navStack.at(-1)?.label || placeholder
                  : placeholder}
              </DialogTitle>
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                className="text-muted-foreground hover:text-foreground"
              >
                <ArrowLeft className="size-4 sm:hidden" />
                <span className="hidden text-sm sm:inline">X</span>
              </button>
            </div>
            {showSearch && (
              <div className="relative mt-2">
                <Search className="text-muted-foreground absolute top-1/2 left-2 size-4 -translate-y-1/2" />
                <Input
                  ref={searchRef}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder={resolvedSearch}
                  className="h-8 pl-8 text-xs"
                />
              </div>
            )}
          </DialogHeader>

          {/* Content */}
          <div className="flex-1 overflow-y-auto px-4 py-2">
            {currentOptions.length === 0 && (
              <p className="text-muted-foreground py-8 text-center text-sm">{resolvedEmpty}</p>
            )}
            <div className="space-y-1">
              {searchQuery
                ? (currentOptions as ReturnType<typeof flattenTree>).map((opt) => (
                    <button
                      key={opt.value}
                      type="button"
                      onClick={() => setTempValue((prev) => (prev === opt.value ? "" : opt.value))}
                      className={cn(
                        "hover:bg-accent flex w-full items-center gap-3 rounded-lg px-3 py-3 text-sm",
                        isRtl ? "text-right" : "text-left",
                        tempValue === opt.value && "bg-accent font-medium",
                        optionClassName,
                      )}
                    >
                      {opt.colorHex && (
                        <span
                          className="inline-block size-5 shrink-0 rounded-full border"
                          style={colorCircleStyle(opt.colorHex)}
                        />
                      )}
                      {opt.icon && <IconRenderer code={opt.icon} className="size-5 shrink-0" />}
                      {opt.path && (
                        <span className="text-muted-foreground text-xs">{opt.path} &gt;</span>
                      )}
                      <span className="flex-1">{opt.label}</span>
                      {tempValue === opt.value && <Check className="text-primary size-4" />}
                    </button>
                  ))
                : (currentOptions as SingleSelectOption[]).map((opt) => {
                    const hasChildren = opt.children && opt.children.length > 0;
                    const isSelected = tempValue === opt.value;
                    return (
                      <button
                        key={opt.value}
                        type="button"
                        onClick={() => {
                          if (hasChildren) {
                            handleOptionClick(opt);
                          } else {
                            setTempValue((prev) => (prev === opt.value ? "" : opt.value));
                          }
                        }}
                        className={cn(
                          "hover:bg-accent flex w-full items-center gap-3 rounded-lg px-3 py-3 text-sm",
                          isRtl ? "text-right" : "text-left",
                          isSelected && !hasChildren && "bg-accent font-medium",
                          optionClassName,
                        )}
                      >
                        {opt.colorHex && (
                          <span
                            className="inline-block size-5 shrink-0 rounded-full border"
                            style={colorCircleStyle(opt.colorHex)}
                          />
                        )}
                        {opt.icon && <IconRenderer code={opt.icon} className="size-5 shrink-0" />}
                        <span className="flex-1" dir={opt.dir}>
                          {opt.label}
                        </span>
                        {opt.imageUrl && (
                          <Image
                            src={opt.imageUrl}
                            alt=""
                            width={32}
                            height={32}
                            className="size-8 shrink-0 rounded object-contain dark:bg-white dark:p-0.5"
                          />
                        )}
                        {isSelected && !hasChildren && <Check className="text-primary size-4" />}
                        {hasChildren &&
                          (isRtl ? (
                            <ChevronLeft className="size-4 shrink-0 opacity-50" />
                          ) : (
                            <ChevronRight className="size-4 shrink-0 opacity-50" />
                          ))}
                      </button>
                    );
                  })}
            </div>
          </div>

          {/* Footer */}
          <DialogFooter className="mx-0 mb-0 shrink-0 flex-row gap-2 border-t px-4 py-3">
            <Button variant="outline" onClick={handleCancel} className="flex-1 gap-1">
              {isRtl ? <ChevronRight className="size-4" /> : <ArrowLeft className="size-4" />}
              {resolvedCancel}
            </Button>
            {value && (
              <Button
                variant="outline"
                onClick={() => {
                  onChange("");
                  setIsOpen(false);
                }}
                className="flex-1 gap-1"
              >
                <Eraser className="size-4" />
                {tCommon("clear")}
              </Button>
            )}
            <Button onClick={handleSelect} className="flex-1 gap-1">
              <Check className="size-4" />
              {resolvedSelect}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
