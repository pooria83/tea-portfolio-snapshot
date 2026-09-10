"use client";

import { memo } from "react";
import { FileJson2Icon } from "lucide-react";

import type { ChatMessage } from "@/types/api";

export const DebugButton = memo(function DebugButton({
  debug,
  label,
  onOpen,
}: {
  debug: ChatMessage["debug"];
  label: string;
  onOpen: (debug: ChatMessage["debug"]) => void;
}) {
  if (!debug) {
    return null;
  }
  return (
    <button
      type="button"
      data-slot="debug-button"
      onClick={() => onOpen(debug)}
      aria-label={label}
      title={label}
      className="text-muted-foreground hover:text-foreground inline-flex w-fit items-center gap-1 text-xs"
    >
      <FileJson2Icon className="size-3.5" />
      {label}
    </button>
  );
});
