"use client";

import { useLocale } from "next-intl";
import { ArrowUpIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

export function ChatInput({
  value,
  onChange,
  onSubmit,
  sendLabel,
  disabled,
  inputPlaceholder,
  className,
}: {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  sendLabel: string;
  disabled: boolean;
  inputPlaceholder: string;
  className?: string;
}) {
  const locale = useLocale();
  const isEnglish = locale === "en";

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
      className={`relative mx-auto w-full max-w-[800px] ${className ?? ""}`}
    >
      <div className="relative">
        <Button
          type="submit"
          disabled={disabled || !value.trim()}
          aria-label={sendLabel}
          size="icon"
          className={`absolute bottom-4 rounded-full ${isEnglish ? "right-4" : "left-4"}`}
        >
          <ArrowUpIcon />
        </Button>
        <Textarea
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              onSubmit();
            }
          }}
          placeholder={inputPlaceholder}
          aria-label={inputPlaceholder}
          className={`min-h-[7.5rem] w-full resize-none border-0 ${isEnglish ? "pr-16" : "pl-16"} focus-visible:border-0 focus-visible:ring-0`}
        />
      </div>
    </form>
  );
}
