"use client";

import { memo, useState } from "react";
import { CheckIcon, CopyIcon } from "lucide-react";

import { copyTextToClipboard } from "@/lib/chat";

export const CopyButton = memo(function CopyButton({
  text,
  label,
  copiedLabel,
}: {
  text: string;
  label: string;
  copiedLabel: string;
}) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    void copyTextToClipboard(text).then((ok) => {
      if (ok) {
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1500);
      }
    });
  }

  return (
    <button
      type="button"
      data-slot="copy-button"
      onClick={handleCopy}
      aria-label={copied ? copiedLabel : label}
      title={label}
      className="text-muted-foreground hover:text-foreground inline-flex w-fit items-center gap-1 text-xs"
    >
      {copied ? <CheckIcon className="size-3.5" /> : <CopyIcon className="size-3.5" />}
      {copied && <span>{copiedLabel}</span>}
    </button>
  );
});
