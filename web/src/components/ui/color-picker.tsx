"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

export interface ColorOption {
  id: string;
  colorHex: string | null;
  label: string;
  colorFamily: string | null;
  isMajor: boolean;
  sortOrder: number;
}

interface ColorPickerProps {
  options: ColorOption[];
  value: string;
  onChange: (id: string) => void;
}

function ColorSwatchCircle({ colorHex, selected }: { colorHex: string; selected: boolean }) {
  return (
    <span
      className={cn(
        "border-border focus-visible:ring-ring block size-12 cursor-pointer rounded-full border transition-all focus-visible:ring-2 focus-visible:outline-none",
        selected && "ring-ring ring-2 ring-offset-2",
      )}
      style={{ backgroundColor: colorHex || "#ccc" }}
    />
  );
}

export function ColorPicker({ options, value, onChange }: ColorPickerProps) {
  const t = useTranslations("colorFamilies");
  const [open, setOpen] = useState(false);

  const groups = new Map<string, ColorOption[]>();
  for (const opt of options) {
    const family = opt.colorFamily || "specialty";
    if (!groups.has(family)) groups.set(family, []);
    const group = groups.get(family);
    if (group) group.push(opt);
  }

  const sortedGroups = Array.from(groups.entries()).toSorted((a, b) => {
    const aOrder = a[1][0]?.sortOrder ?? 0;
    const bOrder = b[1][0]?.sortOrder ?? 0;
    return aOrder - bOrder;
  });

  const selectedOpt = options.find((o) => o.id === value);

  return (
    <>
      <Button type="button" variant="outline" onClick={() => setOpen(true)} className="h-9 gap-2">
        {selectedOpt ? (
          <>
            <span
              className="inline-block size-5 shrink-0 rounded-full border"
              style={{ backgroundColor: selectedOpt.colorHex || "#ccc" }}
            />
            <span>{selectedOpt.label}</span>
          </>
        ) : (
          <span>{t("selectColor")}</span>
        )}
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[80vh] overflow-y-auto sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{t("allColors")}</DialogTitle>
          </DialogHeader>
          <div className="space-y-5">
            {sortedGroups.map(([family, opts]) => (
              <div key={family}>
                <h4 className="text-muted-foreground mb-2 text-xs font-medium tracking-wide uppercase">
                  {t(family)}
                </h4>
                <div className="flex flex-wrap gap-2">
                  {opts.map((opt) => (
                    <button
                      key={opt.id}
                      type="button"
                      onClick={() => {
                        onChange(opt.id);
                        setOpen(false);
                      }}
                      className="flex flex-col items-center gap-0.5"
                    >
                      <ColorSwatchCircle
                        colorHex={opt.colorHex || "#ccc"}
                        selected={value === opt.id}
                      />
                      <span className="text-muted-foreground max-w-24 truncate text-sm leading-tight">
                        {opt.label}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
