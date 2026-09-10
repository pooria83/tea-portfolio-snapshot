"use client";

import { memo, useCallback } from "react";
import { useLocale, useTranslations } from "next-intl";
import { MessageSquarePlusIcon, XIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ConversationList } from "@/components/chat/ConversationList";
import type { ConversationItem } from "@/types/api";

interface ChatSidebarProps {
  conversations: ConversationItem[] | undefined;
  loading: boolean;
  activeId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onNewChat: () => void;
  creating: boolean;
}

export const ChatSidebar = memo(function ChatSidebar({
  conversations,
  loading,
  activeId,
  open,
  onOpenChange,
  onSelect,
  onDelete,
  onNewChat,
  creating,
}: ChatSidebarProps) {
  const t = useTranslations("admin.productSearch");
  const commonT = useTranslations("common");
  const locale = useLocale();

  const handleOverlaySelect = useCallback(
    (id: string) => {
      onSelect(id);
      onOpenChange(false);
    },
    [onSelect, onOpenChange],
  );

  const list = (onSelectId: (id: string) => void) => (
    <ConversationList
      conversations={conversations}
      loading={loading}
      activeId={activeId}
      locale={locale}
      t={t}
      onSelect={onSelectId}
      onDelete={onDelete}
    />
  );

  return (
    <>
      <aside className="border-border hidden w-72 shrink-0 flex-col border-e md:flex">
        <div className="p-3">
          <Button type="button" onClick={onNewChat} className="w-full" disabled={creating}>
            <MessageSquarePlusIcon className="size-4" />
            {t("newChat")}
          </Button>
        </div>
        {list(onSelect)}
      </aside>

      {open && (
        <div className="fixed inset-0 z-50 md:hidden">
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => onOpenChange(false)}
            aria-hidden
          />
          <div className="bg-background absolute inset-y-0 start-0 flex w-72 max-w-[85vw] flex-col border-e shadow-xl">
            <div className="flex items-center gap-2 p-3">
              <Button type="button" onClick={onNewChat} className="flex-1" disabled={creating}>
                <MessageSquarePlusIcon className="size-4" />
                {t("newChat")}
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => onOpenChange(false)}
                aria-label={commonT("close")}
              >
                <XIcon className="size-4" />
              </Button>
            </div>
            {list(handleOverlaySelect)}
          </div>
        </div>
      )}
    </>
  );
});
