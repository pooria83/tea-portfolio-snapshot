"use client";

import { memo } from "react";
import { Trash2Icon } from "lucide-react";

import { relativeTime } from "@/lib/chat";
import { cn } from "@/lib/utils";
import type { ConversationItem } from "@/types/api";

const ConversationRow = memo(function ConversationRow({
  conversation,
  activeId,
  locale,
  t,
  onSelect,
  onDelete,
}: {
  conversation: ConversationItem;
  activeId: string | null;
  locale: string;
  t: (key: string) => string;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  return (
    <div
      className={cn(
        "flex w-full items-center gap-1 rounded-lg p-2",
        conversation.id === activeId ? "bg-accent" : "hover:bg-muted",
      )}
    >
      <button
        type="button"
        onClick={() => onSelect(conversation.id)}
        className="min-w-0 flex-1 text-start"
      >
        <p className="truncate text-sm font-medium">{conversation.title ?? t("newChat")}</p>
        <p className="text-muted-foreground flex items-center gap-1.5 text-xs">
          {conversation.status === "closed" && (
            <span className="bg-muted rounded px-1">{t("closedBadge")}</span>
          )}
          {relativeTime(conversation.last_activity_at, locale)}
        </p>
      </button>
      <button
        type="button"
        onClick={() => onDelete(conversation.id)}
        aria-label={t("deleteChat")}
        className="text-muted-foreground hover:text-destructive shrink-0"
      >
        <Trash2Icon className="size-4" />
      </button>
    </div>
  );
});

export const ConversationList = memo(function ConversationList({
  conversations,
  loading,
  activeId,
  locale,
  t,
  onSelect,
  onDelete,
}: {
  conversations: ConversationItem[] | undefined;
  loading: boolean;
  activeId: string | null;
  locale: string;
  t: (key: string) => string;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-2">
      {loading && (
        <div className="text-muted-foreground flex justify-center p-4 text-xs">{t("loading")}</div>
      )}

      {conversations?.map((conversation) => (
        <ConversationRow
          key={conversation.id}
          conversation={conversation}
          activeId={activeId}
          locale={locale}
          t={t}
          onSelect={onSelect}
          onDelete={onDelete}
        />
      ))}

      {!loading && conversations?.length === 0 && (
        <p className="text-muted-foreground p-4 text-center text-xs">{t("noConversations")}</p>
      )}
    </div>
  );
});
