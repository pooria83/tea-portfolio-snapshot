"use client";

import type { ReactNode } from "react";

export function ImageCropDialog({ open, children }: { open: boolean; children: ReactNode }) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[1001] flex items-start justify-center overflow-y-auto bg-black/50 pt-8 pb-8">
      <div className="bg-popover text-popover-foreground ring-foreground/10 my-auto w-full max-w-lg rounded-xl p-4 ring-1">
        {children}
      </div>
    </div>
  );
}
