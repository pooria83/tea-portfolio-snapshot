"use client";

import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { ChatMessage } from "@/types/api";

export function DebugDialog({
  debug,
  onClose,
}: {
  debug: ChatMessage["debug"];
  onClose: () => void;
}) {
  const t = useTranslations("admin.productSearch");
  const commonT = useTranslations("common");

  return (
    <Dialog
      open={debug != null}
      onOpenChange={(open) => {
        if (!open) {
          onClose();
        }
      }}
    >
      <DialogContent
        showCloseButton={false}
        className="flex max-h-[85vh] flex-col overflow-hidden sm:max-w-3xl"
      >
        <DialogHeader>
          <DialogTitle>{t("debugTitle")}</DialogTitle>
        </DialogHeader>
        <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto">
          <div className="flex flex-col gap-1.5">
            <h3 className="text-sm font-medium">{t("debugPrompt")}</h3>
            <pre className="bg-muted max-h-64 overflow-auto rounded-lg p-3 font-mono text-xs break-words whitespace-pre-wrap">
              {JSON.stringify(debug?.prompt, null, 2)}
            </pre>
          </div>
          <div className="flex flex-col gap-1.5">
            <h3 className="text-sm font-medium">{t("debugResponse")}</h3>
            <pre className="bg-muted max-h-64 overflow-auto rounded-lg p-3 font-mono text-xs break-words whitespace-pre-wrap">
              {JSON.stringify(debug?.response, null, 2)}
            </pre>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            {commonT("close")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
