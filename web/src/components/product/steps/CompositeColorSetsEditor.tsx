"use client";

import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { ColorPicker } from "@/components/ui/color-picker";
import { FiPlus, FiTrash2 } from "react-icons/fi";
import type { ProductPieceInput, ProductColorSetInput } from "@/types/api";

export interface ColorOptionItem {
  id: string;
  colorHex: string | null;
  label: string;
  colorFamily: string | null;
  isMajor: boolean;
  sortOrder: number;
}

interface CompositeColorSetsEditorProps {
  pieces: (ProductPieceInput & { id?: string })[];
  colorSets: ProductColorSetInput[];
  onChange: (sets: ProductColorSetInput[]) => void;
  colorOptions: ColorOptionItem[];
}

export function CompositeColorSetsEditor({
  pieces,
  colorSets,
  onChange,
  colorOptions,
}: CompositeColorSetsEditorProps) {
  const t = useTranslations("product");

  if (pieces.length === 0) {
    return (
      <div className="text-muted-foreground rounded-lg border border-dashed p-6 text-center text-sm">
        {t("noPiecesToColor") || "Define pieces in Basic Info first"}
      </div>
    );
  }

  const updateCell = (setIndex: number, pieceIdx: number, colorOptionId: string) => {
    const next = colorSets.map((set, si) => {
      if (si !== setIndex) return set;
      const newValues = set.values.map((v, vi) =>
        vi === pieceIdx ? { ...v, color_option_id: colorOptionId } : v,
      );
      return { ...set, values: newValues };
    });
    onChange(next);
  };

  const removeSet = (index: number) => {
    onChange(colorSets.filter((_, i) => i !== index));
  };

  const addSet = () => {
    onChange([
      ...colorSets,
      {
        sort_order: colorSets.length,
        values: pieces.map((_, i) => ({
          piece_id: String(i),
          color_option_id: "",
        })),
      },
    ]);
  };

  const getColorPickerValue = (setIndex: number, pieceIdx: number): string => {
    const set = colorSets[setIndex];
    if (!set) return "";
    const val = set.values[pieceIdx];
    return val?.color_option_id || "";
  };

  const getPieceLabel = (piece: ProductPieceInput & { id?: string }, idx: number): string => {
    return piece.name_en || piece.name_ar || `Piece ${idx + 1}`;
  };

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">{t("colorSets") || "Color Sets"}</h2>
      <p className="text-muted-foreground text-xs">
        {t("colorSetsDesc") ||
          "Each row is an atomic color combination. Customers can only buy colors within the same row."}
      </p>

      <div className="space-y-3">
        {colorSets.map((_set, si) => (
          <div key={si} className="relative rounded-lg border p-4">
            <button
              type="button"
              onClick={() => removeSet(si)}
              className="text-destructive hover:bg-destructive/10 absolute top-2 right-2 flex size-7 items-center justify-center rounded-md transition-colors"
            >
              <FiTrash2 className="size-4" />
            </button>

            <div
              className="grid gap-3 pt-2"
              style={{ gridTemplateColumns: `repeat(${pieces.length}, 1fr)` }}
            >
              {pieces.map((piece, pi) => (
                <div key={pi} className="space-y-1.5">
                  <label className="text-muted-foreground block text-xs font-medium">
                    {getPieceLabel(piece, pi)}
                  </label>
                  <ColorPicker
                    options={colorOptions}
                    value={getColorPickerValue(si, pi)}
                    onChange={(id) => updateCell(si, pi, id)}
                  />
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <Button type="button" variant="outline" size="sm" onClick={addSet} className="gap-1">
        <FiPlus className="size-4" />
        {t("addColorSet") || "Add Color Set"}
      </Button>
    </div>
  );
}
