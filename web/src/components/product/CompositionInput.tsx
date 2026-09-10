"use client";

import { useState, useCallback } from "react";
import { SingleSelect } from "@/components/ui/single-select";
import { Slider } from "@/components/ui/slider";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

interface CompositionOption {
  value: string;
  label: string;
}

interface CompositionEntry {
  material: string;
  percentage: number;
}

interface CompositionInputProps {
  options: CompositionOption[];
  value: string;
  onChange: (value: string | null) => void;
  placeholder?: string;
}

function initState(value: string) {
  if (!value) {
    return { isComposite: false, mat1: "", mat2: "", pct1: 50, pct2: 50 };
  }
  try {
    const parsed = JSON.parse(value) as CompositionEntry[];
    if (Array.isArray(parsed) && parsed.length === 2) {
      const entry1 = parsed[0];
      const entry2 = parsed[1];
      if (entry1 && entry2) {
        return {
          isComposite: true,
          mat1: entry1.material,
          pct1: entry1.percentage,
          mat2: entry2.material,
          pct2: entry2.percentage,
        };
      }
    }
  } catch (error) {
    console.warn("Failed to parse composition value:", error);
  }
  return { isComposite: false, mat1: value, mat2: "", pct1: 50, pct2: 50 };
}

export function CompositionInput({
  options,
  value: _value,
  onChange,
  placeholder,
}: CompositionInputProps) {
  const [state, setState] = useState(() => initState(_value));
  const { isComposite, mat1, mat2, pct1, pct2 } = state;

  const emitComposite = useCallback(
    (m1: string, p1: number, m2: string, p2: number) => {
      if (!m1 || !m2 || m1 === m2 || p1 + p2 !== 100) return;
      onChange(
        JSON.stringify([
          { material: m1, percentage: p1 },
          { material: m2, percentage: p2 },
        ]),
      );
    },
    [onChange],
  );

  const handleCompositeToggle = (checked: boolean) => {
    if (checked) {
      setState((prev) => ({ ...prev, isComposite: true }));
    } else {
      setState((prev) => ({ ...prev, isComposite: false }));
      onChange(mat1 || null);
    }
  };

  const handleMat1Change = (v: string) => {
    const next = { ...state, mat1: v };
    setState(next);
    if (
      next.isComposite &&
      next.mat1 &&
      next.mat2 &&
      next.mat1 !== next.mat2 &&
      next.pct1 + next.pct2 === 100
    ) {
      onChange(
        JSON.stringify([
          { material: next.mat1, percentage: next.pct1 },
          { material: next.mat2, percentage: next.pct2 },
        ]),
      );
    }
  };

  const handleMat2Change = (v: string) => {
    const next = { ...state, mat2: v };
    setState(next);
    if (
      next.isComposite &&
      next.mat1 &&
      next.mat2 &&
      next.mat1 !== next.mat2 &&
      next.pct1 + next.pct2 === 100
    ) {
      onChange(
        JSON.stringify([
          { material: next.mat1, percentage: next.pct1 },
          { material: next.mat2, percentage: next.pct2 },
        ]),
      );
    }
  };

  const handlePct1Change = (raw: number | readonly number[]) => {
    const newPct1 = Array.isArray(raw) ? (raw[0] ?? 50) : raw;
    const newPct2 = 100 - newPct1;
    const next = { ...state, pct1: newPct1, pct2: newPct2 };
    setState(next);
    if (next.mat1 && next.mat2 && next.mat1 !== next.mat2) {
      emitComposite(next.mat1, next.pct1, next.mat2, next.pct2);
    }
  };

  const handlePct2Change = (raw: number | readonly number[]) => {
    const newPct2 = Array.isArray(raw) ? (raw[0] ?? 50) : raw;
    const newPct1 = 100 - newPct2;
    const next = { ...state, pct1: newPct1, pct2: newPct2 };
    setState(next);
    if (next.mat1 && next.mat2 && next.mat1 !== next.mat2) {
      emitComposite(next.mat1, next.pct1, next.mat2, next.pct2);
    }
  };

  const handlePctInput1 = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = Math.max(1, Math.min(99, Number(e.target.value) || 0));
    handlePct1Change([v]);
  };

  const handlePctInput2 = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = Math.max(1, Math.min(99, Number(e.target.value) || 0));
    handlePct2Change([v]);
  };

  const total = pct1 + pct2;
  const hasConflict = mat1 === mat2 && mat1 !== "";
  const remainingOptions = (excludeId: string) => options.filter((o) => o.value !== excludeId);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Switch checked={isComposite} onCheckedChange={handleCompositeToggle} />
        <Label className="text-sm">Composite material</Label>
      </div>

      {isComposite ? (
        <div className="space-y-4 rounded-lg border p-3">
          <div className="space-y-2">
            <Label className="text-muted-foreground text-xs">Material 1</Label>
            <div className="flex items-center gap-3">
              <div className="flex-1">
                <SingleSelect
                  options={options}
                  value={mat1}
                  onChange={handleMat1Change}
                  placeholder="Select material"
                />
              </div>
              <div className="flex w-28 shrink-0 items-center gap-1">
                <Slider
                  value={[pct1]}
                  min={1}
                  max={99}
                  onValueChange={handlePct1Change}
                  className="flex-1"
                />
                <Input
                  type="number"
                  min={1}
                  max={99}
                  value={pct1}
                  onChange={handlePctInput1}
                  className="h-7 w-14 [appearance:textfield] text-center text-xs [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                />
                <span className="text-xs">%</span>
              </div>
            </div>
          </div>

          <div className="space-y-2">
            <Label className="text-muted-foreground text-xs">Material 2</Label>
            <div className="flex items-center gap-3">
              <div className="flex-1">
                <SingleSelect
                  options={remainingOptions(mat1)}
                  value={mat2}
                  onChange={handleMat2Change}
                  placeholder="Select material"
                />
              </div>
              <div className="flex w-28 shrink-0 items-center gap-1">
                <Slider
                  value={[pct2]}
                  min={1}
                  max={99}
                  onValueChange={handlePct2Change}
                  className="flex-1"
                />
                <Input
                  type="number"
                  min={1}
                  max={99}
                  value={pct2}
                  onChange={handlePctInput2}
                  className="h-7 w-14 [appearance:textfield] text-center text-xs [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                />
                <span className="text-xs">%</span>
              </div>
            </div>
          </div>

          <div
            className={cn(
              "flex items-center justify-between text-xs",
              total === 100 && !hasConflict ? "text-green-600" : "text-destructive",
            )}
          >
            <span>
              Total: {total}%{total === 100 ? " \u2713" : " (must equal 100)"}
            </span>
            {hasConflict && <span>Materials must be different</span>}
          </div>
        </div>
      ) : (
        <SingleSelect
          options={options}
          value={mat1}
          onChange={(v) => {
            setState((prev) => ({ ...prev, mat1: v }));
            onChange(v || null);
          }}
          placeholder={placeholder}
        />
      )}
    </div>
  );
}
