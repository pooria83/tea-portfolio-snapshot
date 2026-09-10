"use client";

import { useCallback } from "react";
import { useTranslations } from "next-intl";
import { Dialog, DialogContent, DialogClose } from "@/components/ui/dialog";
import { useCloseOnBack } from "@/hooks/useCloseOnBack";
import { Button } from "@/components/ui/button";
import { XIcon } from "lucide-react";
import { ProductView } from "@/components/product/ProductView";
import type { ProductResponse } from "@/types/api";

interface ProductViewDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  storeId: string;
  productId: string;
  initialData?: ProductResponse;
}

export function ProductViewDialog({
  open,
  onOpenChange,
  storeId,
  productId,
  initialData,
}: ProductViewDialogProps) {
  const tCommon = useTranslations("common");
  const closeDialog = useCallback(() => onOpenChange(false), [onOpenChange]);
  useCloseOnBack(open, closeDialog, "product-view");
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        showCloseButton={false}
        className="flex max-h-dvh flex-col overflow-hidden p-0 [overflow-wrap:break-word] break-words max-sm:inset-0 max-sm:!top-0 max-sm:!left-0 max-sm:m-0 max-sm:max-h-full max-sm:w-full max-sm:!max-w-full max-sm:!translate-x-0 max-sm:!translate-y-0 max-sm:rounded-none sm:max-h-[85vh] sm:max-w-3xl lg:max-w-5xl"
      >
        <div className="flex shrink-0 items-center justify-between border-b px-4 py-2.5">
          <span className="text-sm font-semibold">Product Details</span>
          <DialogClose
            render={
              <Button variant="ghost" size="icon-sm">
                <XIcon />
              </Button>
            }
          />
        </div>
        <div className="flex-1 overflow-y-auto">
          <ProductView
            storeId={storeId}
            productId={productId}
            {...(initialData ? { initialData } : {})}
          />
        </div>
        <div className="flex shrink-0 items-center justify-end border-t px-4 py-3">
          <DialogClose
            render={
              <Button variant="outline" className="w-full">
                {tCommon("close")}
              </Button>
            }
          />
        </div>
      </DialogContent>
    </Dialog>
  );
}
