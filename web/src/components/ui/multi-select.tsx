"use client";

import { useState, useEffect, useRef, useMemo } from "react";
import { Search, X, ChevronDown, ArrowLeft, ArrowRight, Check } from "lucide-react";
import { useTranslations, useLocale } from "next-intl";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";

export interface MultiSelectOption {
  value: string;
  label: string;
  colorHex?: string | undefined;
  colorFamily?: string | undefined;
}

interface MultiSelectProps {
  options: MultiSelectOption[];
  value: string[];
  onChange: (value: string[]) => void;
  placeholder?: string;
  searchPlaceholder?: string;
  emptyMessage?: string;
}

export function MultiSelect({
  options,
  value,
  onChange,
  placeholder = "Select...",
  searchPlaceholder = "Search...",
  emptyMessage = "No options",
}: MultiSelectProps) {
  const locale = useLocale();
  const isRtl = locale === "ar" || locale === "fa";
  const tColor = useTranslations("colorFamilies");
  const tCommon = useTranslations("common");
  const resolvedSearch =
    searchPlaceholder === "Search..." ? tCommon("searchOptions") : searchPlaceholder;
  const resolvedEmpty = emptyMessage === "No options" ? tCommon("noOptions") : emptyMessage;
  const [isOpen, setIsOpen] = useState(false);
  const [selectedIds, setSelectedIds] = useState<string[]>(value);
  const [searchQuery, setSearchQuery] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      setSelectedIds(value);
      setSearchQuery("");
    }
  }, [isOpen, value]);

  useEffect(() => {
    if (isOpen && options.length > 5) {
      searchRef.current?.focus();
    }
  }, [isOpen, options.length]);

  const hasColorFamilies = useMemo(() => options.some((o) => o.colorFamily), [options]);

  const groupedOptions = useMemo(() => {
    if (!hasColorFamilies) return null;
    const groups = new Map<string, MultiSelectOption[]>();
    for (const opt of options) {
      const family = opt.colorFamily || "specialty";
      if (!groups.has(family)) groups.set(family, []);
      const group = groups.get(family);
      if (group) group.push(opt);
    }
    return Array.from(groups.entries());
  }, [options, hasColorFamilies]);

  const filteredGroups = useMemo(() => {
    if (!groupedOptions) return null;
    return groupedOptions
      .map(
        ([family, opts]) =>
          [
            family,
            searchQuery
              ? opts.filter((o) => o.label.toLowerCase().includes(searchQuery.toLowerCase()))
              : opts,
          ] as const,
      )
      .filter(([, opts]) => opts.length > 0);
  }, [groupedOptions, searchQuery]);

  const filteredOptions = useMemo(
    () =>
      searchQuery
        ? options.filter((o) => o.label.toLowerCase().includes(searchQuery.toLowerCase()))
        : options,
    [options, searchQuery],
  );

  const showSearch = options.length > 5;

  const toggleOption = (id: string) => {
    setSelectedIds((prev) => {
      if (prev.includes(id)) return prev.filter((v) => v !== id);
      return [...prev, id];
    });
    setSearchQuery("");
  };

  const removeSelected = (id: string) => {
    setSelectedIds((prev) => prev.filter((v) => v !== id));
  };

  const handleApply = () => {
    onChange(selectedIds);
    setIsOpen(false);
  };

  const handleBack = () => {
    setIsOpen(false);
  };

  const labelMap = useMemo(() => new Map(options.map((o) => [o.value, o.label])), [options]);
  const colorMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const opt of options) {
      if (opt.colorHex) map.set(opt.value, opt.colorHex);
    }
    return map;
  }, [options]);

  const selectedLabels = useMemo(
    () => selectedIds.map((id) => ({ id, label: labelMap.get(id) || id, color: colorMap.get(id) })),
    [selectedIds, labelMap, colorMap],
  );

  const triggerLabels = useMemo(
    () => value.map((id) => ({ id, label: labelMap.get(id) || id, color: colorMap.get(id) })),
    [value, labelMap, colorMap],
  );

  return (
    <>
      {/* Trigger */}
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        className={cn(
          "border-input flex min-h-9 w-full flex-wrap items-center gap-1.5 rounded-lg border bg-transparent px-2.5 py-1.5 text-sm shadow-xs transition-colors",
          "focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]",
          "hover:bg-accent hover:text-accent-foreground",
          "disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50",
          value.length === 0 && "text-muted-foreground",
        )}
      >
        {value.length === 0 ? (
          <span className={cn("flex-1", isRtl ? "text-right" : "text-left")}>{placeholder}</span>
        ) : (
          triggerLabels.map(({ id, label, color }) => (
            <span
              key={id}
              className="bg-secondary text-secondary-foreground inline-flex h-5 items-center gap-0.5 rounded-full px-1.5 text-xs font-medium"
            >
              {color && (
                <span
                  className="inline-block size-3 shrink-0 rounded-full"
                  style={colorCircleStyle(color)}
                />
              )}
              {label}
              <span
                role="button"
                tabIndex={0}
                onClick={(e) => {
                  e.stopPropagation();
                  onChange(value.filter((v) => v !== id));
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.stopPropagation();
                    onChange(value.filter((v) => v !== id));
                  }
                }}
                className="hover:text-foreground text-secondary-foreground/60 cursor-pointer"
              >
                <X className="size-3" />
              </span>
            </span>
          ))
        )}
        <ChevronDown className="ml-auto size-4 shrink-0 opacity-50" />
      </button>

      {/* Dialog */}
      <Dialog open={isOpen} onOpenChange={setIsOpen}>
        <DialogContent
          showCloseButton={false}
          className={cn(
            "flex flex-col gap-0 p-0",
            "fixed inset-0 max-h-none max-w-none translate-x-0 translate-y-0 rounded-none",
            "sm:top-1/2 sm:left-1/2 sm:max-h-[80dvh] sm:max-w-lg sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-xl",
          )}
        >
          {/* Header */}
          <DialogHeader className="shrink-0 border-b px-4 py-3">
            <div className="flex items-center justify-between">
              <DialogTitle className="text-base">{placeholder}</DialogTitle>
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                className="text-muted-foreground hover:text-foreground"
              >
                <X className="size-4" />
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
            {selectedLabels.length > 0 && (
              <div className="mb-3 flex flex-wrap gap-1.5">
                {selectedLabels.map(({ id, label, color }) => (
                  <span
                    key={id}
                    className="bg-primary/10 text-primary inline-flex h-6 items-center gap-0.5 rounded-full px-2 text-xs font-medium"
                  >
                    {color && (
                      <span
                        className="inline-block size-3.5 shrink-0 rounded-full border"
                        style={colorCircleStyle(color)}
                      />
                    )}
                    {label}
                    <button
                      type="button"
                      onClick={() => removeSelected(id)}
                      className="hover:text-primary/80 text-primary/60"
                    >
                      <X className="size-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}
            <div className="space-y-1">
              {!filteredGroups && filteredOptions.length === 0 && (
                <p className="text-muted-foreground py-8 text-center text-sm">{resolvedEmpty}</p>
              )}
              {filteredGroups?.map(([family, opts]) => (
                <div key={family}>
                  <h4 className="text-muted-foreground px-2 py-2 text-xs font-medium tracking-wide uppercase">
                    {tColor(family)}
                  </h4>
                  {opts.map((opt) => (
                    <OptionRow
                      key={opt.value}
                      opt={opt}
                      selectedIds={selectedIds}
                      toggleOption={toggleOption}
                    />
                  ))}
                </div>
              ))}
              {!filteredGroups &&
                filteredOptions.map((opt) => (
                  <OptionRow
                    key={opt.value}
                    opt={opt}
                    selectedIds={selectedIds}
                    toggleOption={toggleOption}
                  />
                ))}
            </div>
          </div>

          {/* Footer */}
          <DialogFooter className="mx-0 mb-0 shrink-0 flex-row gap-2 border-t px-4 py-3">
            <Button variant="outline" onClick={handleBack} className="flex-1 gap-1">
              {isRtl ? <ArrowRight className="size-4" /> : <ArrowLeft className="size-4" />}
              {tCommon("back")}
            </Button>
            <Button onClick={handleApply} className="flex-1 gap-1">
              <Check className="size-4" />
              {tCommon("select")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
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

function OptionRow({
  opt,
  selectedIds,
  toggleOption,
}: {
  opt: MultiSelectOption;
  selectedIds: string[];
  toggleOption: (id: string) => void;
}) {
  return (
    <label className="hover:bg-accent flex cursor-pointer items-center gap-3 rounded-lg px-3 py-3 text-sm">
      <Checkbox
        checked={selectedIds.includes(opt.value)}
        onCheckedChange={() => toggleOption(opt.value)}
      />
      {opt.colorHex && (
        <span
          className="inline-block size-5 shrink-0 rounded-full border"
          style={colorCircleStyle(opt.colorHex)}
        />
      )}
      <span className="flex-1">{opt.label}</span>
    </label>
  );
}
