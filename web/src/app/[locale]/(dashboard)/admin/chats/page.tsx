"use client";

import { useCallback, useMemo, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useGetAdminChatMessagesQuery, useGetAdminChatsQuery } from "@/store/api/adminApi";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DataTable, type DataTableColumn } from "@/components/ui/data-table";
import { PaginationBar } from "@/components/ui/pagination-bar";
import { usePaginationTable } from "@/hooks/usePaginationTable";
import { RetryingThumbnail } from "@/components/chat/RetryingThumbnail";
import { localeValue } from "@/lib/locale";
import type {
  AdminChatMessage,
  AdminChatMessageProductSnapshot,
  AdminConversationItem,
} from "@/types/api";

const PAGE_SIZE = 20;

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString();
}

function MessageBubble({ message }: { message: AdminChatMessage }) {
  const t = useTranslations("settings.chats");
  const locale = useLocale();
  const messageLocale = message.locale || locale;
  const isUser = message.role === "user";
  const isFailed = message.status === "failed";

  function snapshotName(p: AdminChatMessageProductSnapshot): string {
    return (
      localeValue(messageLocale, p.name_ar ?? "", p.name_fa ?? "", p.name_en ?? "") ||
      p.name ||
      p.id
    );
  }
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] min-w-0 rounded-lg border p-3 break-words ${isUser ? "bg-primary/10" : "bg-muted"}`}
      >
        <div className="mb-1 flex min-w-0 items-center justify-between gap-3 break-words">
          <span className="text-muted-foreground text-xs font-semibold">
            {isUser ? t("roleUser") : t("roleAssistant")}
          </span>
          <div className="flex shrink-0 items-center gap-2">
            {isFailed && <Badge variant="destructive">{t("failed")}</Badge>}
            <span className="text-muted-foreground text-xs">{formatDate(message.created_at)}</span>
          </div>
        </div>
        <p className="text-sm [overflow-wrap:anywhere] whitespace-pre-wrap">
          {message.content || "—"}
        </p>
        {message.product_snapshots.length > 0 && (
          <div className="mt-2 space-y-1.5">
            <p className="text-muted-foreground text-xs font-semibold">{t("products")}</p>
            {message.product_snapshots.map((p) => (
              <div
                key={p.id}
                className="bg-background flex items-center gap-2 rounded-md border p-1.5"
              >
                <div className="bg-muted flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded">
                  {p.image_url ? (
                    <RetryingThumbnail src={p.image_url} alt={snapshotName(p)} />
                  ) : (
                    <span className="text-muted-foreground text-xs">—</span>
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium" dir="auto">
                    {snapshotName(p)}
                  </p>
                  {p.brand && (
                    <p className="text-muted-foreground truncate text-xs" dir="auto">
                      {localeValue(
                        messageLocale,
                        p.brand_ar ?? "",
                        p.brand_fa ?? "",
                        p.brand_en ?? "",
                      ) || p.brand}
                    </p>
                  )}
                </div>
                <div className="shrink-0 text-sm font-medium">
                  {typeof p.price === "number" ? `${p.price.toLocaleString()} ${p.currency}` : "—"}
                </div>
              </div>
            ))}
          </div>
        )}
        {message.feedback && (
          <div className="mt-2 text-xs text-amber-500">
            {t("rating")}: {"★".repeat(message.feedback.rating)}
            {"☆".repeat(5 - message.feedback.rating)}
          </div>
        )}
      </div>
    </div>
  );
}

function ConversationModal({
  conversation,
  open,
  onOpenChange,
}: {
  conversation: AdminConversationItem | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const t = useTranslations("settings.chats");
  const commonT = useTranslations("common");
  const { data: messages, isFetching } = useGetAdminChatMessagesQuery(conversation?.id ?? "", {
    skip: !conversation,
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[80vh] max-w-[95vw] flex-col overflow-hidden [overflow-wrap:anywhere] break-words lg:max-w-[1400px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <span dir="auto">{conversation?.title || t("viewTitle")}</span>
            {conversation && (
              <Badge variant={conversation.status === "active" ? "default" : "secondary"}>
                {conversation.status === "active" ? t("active") : t("closed")}
              </Badge>
            )}
          </DialogTitle>
        </DialogHeader>
        {conversation?.summary && (
          <div className="bg-muted/50 text-muted-foreground rounded-md border p-3 text-sm [overflow-wrap:anywhere] break-words">
            <span className="font-semibold">{t("summary")}: </span>
            {conversation.summary}
          </div>
        )}
        <div className="flex-1 space-y-3 overflow-y-auto p-1">
          {isFetching && (
            <p className="text-muted-foreground text-center text-sm">{commonT("loading")}</p>
          )}
          {messages && messages.length === 0 && (
            <p className="text-muted-foreground text-center text-sm">{t("noMessages")}</p>
          )}
          {messages?.map((m) => (
            <MessageBubble key={m.id} message={m} />
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default function AdminChatsPage() {
  const t = useTranslations("settings.chats");
  const commonT = useTranslations("common");
  const [selected, setSelected] = useState<AdminConversationItem | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const { skip, page, pageSize, next, previous } = usePaginationTable(PAGE_SIZE);

  const { data, isLoading, isFetching, isError } = useGetAdminChatsQuery({
    skip,
    limit: PAGE_SIZE,
  });

  const openDetail = useCallback((item: AdminConversationItem) => {
    setSelected(item);
    setDetailOpen(true);
  }, []);

  const meta = data?.meta;
  const totalPages = meta ? Math.ceil(meta.total / pageSize) : 1;

  const columns = useMemo<DataTableColumn<AdminConversationItem>[]>(
    () => [
      {
        header: t("titleColumn"),
        cell: (item) => (
          <span className="line-clamp-2 font-medium" dir="auto">
            {item.title || "—"}
          </span>
        ),
      },
      {
        header: t("userIdentifier"),
        cell: (item) =>
          item.user_identifier ? (
            <span className="font-medium" dir="auto">
              {item.user_identifier}
            </span>
          ) : (
            <Badge variant="secondary">{t("anonymous")}</Badge>
          ),
      },
      {
        header: t("status"),
        cell: (item) => (
          <Badge variant={item.status === "active" ? "default" : "secondary"}>
            {item.status === "active" ? t("active") : t("closed")}
          </Badge>
        ),
      },
      {
        header: t("messages"),
        cell: (item) => (
          <span className="text-muted-foreground text-sm">{item.user_message_count}</span>
        ),
      },
      {
        header: t("lastActivity"),
        cell: (item) => (
          <span className="text-muted-foreground text-sm">{formatDate(item.last_activity_at)}</span>
        ),
      },
      {
        header: t("locale"),
        cell: (item) => <span className="text-muted-foreground text-sm">{item.locale}</span>,
      },
      {
        header: t("view"),
        align: "right",
        cell: (item) => (
          <Button size="sm" variant="outline" onClick={() => openDetail(item)}>
            {t("view")}
          </Button>
        ),
      },
    ],
    [t, openDetail],
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-12">
        <p className="text-muted-foreground">{commonT("loading")}</p>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 p-12">
        <p className="text-destructive">{commonT("error")}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{t("title")}</h1>
        <p className="text-muted-foreground text-sm">{t("description")}</p>
      </div>

      <DataTable
        columns={columns}
        rows={data?.items}
        rowKey={(item) => item.id}
        emptyText={t("noConversations")}
      />

      <PaginationBar
        page={page}
        totalPages={totalPages}
        canPrevious={page > 1}
        canNext={Boolean(meta?.has_next) && !isFetching}
        onPrevious={previous}
        onNext={next}
        previousLabel={commonT("back")}
        nextLabel={commonT("next")}
        leftContent={
          <span>
            {t("total")}: {meta?.total ?? 0}
          </span>
        }
      />

      {detailOpen && (
        <ConversationModal conversation={selected} open onOpenChange={setDetailOpen} />
      )}
    </div>
  );
}
