"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { MessageSquarePlusIcon, PanelLeftIcon, Trash2Icon } from "lucide-react";

import { useAppDispatch } from "@/store/hooks";
import { baseApi } from "@/store/api/baseApi";
import {
  useCreateConversationMutation,
  useDeleteConversationMutation,
  useGetChatMessagesQuery,
  useGetMyChatsQuery,
} from "@/store/api/chatApi";
import { useChat } from "@/hooks/useChat";
import type { ChatSocketStatus } from "@/hooks/useChatSocket";
import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { ChatMessageList, ChatMessageListLoading } from "@/components/chat/ChatMessageList";
import { DebugDialog } from "@/components/chat/DebugDialog";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogMedia,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Textarea } from "@/components/ui/textarea";
import { ProductViewDialog } from "@/components/product/ProductViewDialog";
import { localeValue } from "@/lib/locale";
import type { ChatMessage, ChatProduct } from "@/types/api";

function ChatComposer({
  status,
  canSend,
  isClosed,
  onSend,
}: {
  status: ChatSocketStatus;
  canSend: boolean;
  isClosed: boolean;
  onSend: (content: string) => void;
}) {
  const t = useTranslations("admin.productSearch");
  const [query, setQuery] = useState("");

  const submitQuery = () => {
    const content = query.trim();
    if (!content || !canSend) {
      return;
    }
    setQuery("");
    onSend(content);
  };

  let sendLabel: string;
  if (status === "open") {
    sendLabel = t("send");
  } else if (status === "connecting") {
    sendLabel = t("connecting");
  } else {
    sendLabel = t("reconnecting");
  }

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        submitQuery();
      }}
      className="flex shrink-0 gap-2 px-6 pt-2 pb-6"
    >
      <Textarea
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            submitQuery();
          }
        }}
        placeholder={t("inputPlaceholder")}
        disabled={isClosed}
        aria-label={t("inputPlaceholder")}
        className="max-h-40 min-h-10 flex-1 resize-none"
      />
      <Button type="submit" disabled={!query.trim() || !canSend}>
        {sendLabel}
      </Button>
    </form>
  );
}

export default function ProductSearchPage() {
  const t = useTranslations("admin.productSearch");
  const commonT = useTranslations("common");
  const locale = useLocale();
  const dispatch = useAppDispatch();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [debugTarget, setDebugTarget] = useState<ChatMessage["debug"]>(null);
  const [selectedProduct, setSelectedProduct] = useState<ChatProduct | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const { data: conversations, isLoading: chatsLoading } = useGetMyChatsQuery();
  const [createConversation, { isLoading: creating }] = useCreateConversationMutation();
  const [deleteConversation] = useDeleteConversationMutation();
  const { data: history, isLoading: historyLoading } = useGetChatMessagesQuery(
    { conversationId: activeId ?? "" },
    { skip: !activeId },
  );

  const activeConversation = useMemo(
    () => conversations?.find((conversation) => conversation.id === activeId) ?? null,
    [conversations, activeId],
  );
  const isClosed = activeConversation?.status === "closed";

  const { messages, status, canSend, streaming, sendMessage, sendSimilar, retry, mergeHistory } =
    useChat({
      conversationId: activeId,
      blocked: isClosed,
      onTurnSaved: () => dispatch(baseApi.util.invalidateTags(["Chats"])),
    });

  useEffect(() => {
    if (history) {
      mergeHistory(history);
    }
  }, [history, mergeHistory]);

  useEffect(() => {
    let cancelled = false;

    async function ensureConversation() {
      if (chatsLoading || activeId) {
        return;
      }
      const active = conversations?.find((conversation) => conversation.status === "active");
      if (active) {
        setActiveId(active.id);
        return;
      }
      try {
        const conversation = await createConversation({ locale, createNew: true }).unwrap();
        if (!cancelled) {
          setActiveId(conversation.id);
        }
      } catch (error) {
        console.warn("chat_create_failed", error);
      }
    }

    void ensureConversation();
    return () => {
      cancelled = true;
    };
  }, [chatsLoading, conversations, activeId, createConversation, locale]);

  const handleSelectConversation = useCallback((conversationId: string) => {
    setActiveId(conversationId);
  }, []);

  const handleNewChat = useCallback(async () => {
    try {
      const conversation = await createConversation({ locale, createNew: true }).unwrap();
      setActiveId(conversation.id);
    } catch (error) {
      console.warn("chat_create_failed", error);
    }
  }, [createConversation, locale]);

  const handleDelete = useCallback(
    async (conversationId: string | null) => {
      if (!conversationId) {
        return;
      }
      setDeleteTarget(null);
      try {
        await deleteConversation(conversationId).unwrap();
        setActiveId((current) => (current === conversationId ? null : current));
      } catch (error) {
        console.warn("chat_delete_failed", error);
      }
    },
    [deleteConversation],
  );

  const handleFindSimilar = useCallback(
    (product: ChatProduct) => {
      const productName =
        localeValue(locale, product.name_ar ?? "", product.name_fa ?? "", product.name_en ?? "") ||
        product.name ||
        "";
      sendSimilar(product, productName);
    },
    [locale, sendSimilar],
  );

  const productViewProps = useMemo(
    () => ({
      open: selectedProduct != null,
      storeId: selectedProduct?.store_id ?? "",
      productId: selectedProduct?.id ?? "",
      onOpenChange: (open: boolean) => {
        if (!open) {
          setSelectedProduct(null);
        }
      },
    }),
    [selectedProduct],
  );

  const loadingNode = useMemo(
    () => (historyLoading && !history ? <ChatMessageListLoading /> : undefined),
    [historyLoading, history],
  );

  const emptyNode = useMemo(
    () =>
      !historyLoading && history?.length === 0 && messages.length === 0 && !streaming ? (
        <div className="text-muted-foreground flex flex-1 items-center justify-center text-sm">
          {t("placeholder")}
        </div>
      ) : undefined,
    [historyLoading, history, messages.length, streaming, t],
  );

  return (
    <div className="-m-6 flex h-[calc(100svh-3.5rem)]">
      <ChatSidebar
        conversations={conversations}
        loading={chatsLoading}
        activeId={activeId}
        open={sidebarOpen}
        onOpenChange={setSidebarOpen}
        onSelect={handleSelectConversation}
        onDelete={setDeleteTarget}
        onNewChat={() => void handleNewChat()}
        creating={creating}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="mb-4 flex shrink-0 items-center justify-between gap-2 px-4 pt-4 md:px-6 md:pt-6">
          <div className="min-w-0">
            <h1 className="truncate text-2xl font-bold tracking-tight">{t("title")}</h1>
            <p className="text-muted-foreground hidden text-sm sm:block">{t("description")}</p>
          </div>
          <div className="flex shrink-0 items-center gap-2 md:hidden">
            <Button
              type="button"
              variant="outline"
              size="icon"
              onClick={() => setSidebarOpen(true)}
              aria-label={t("openConversations")}
            >
              <PanelLeftIcon className="size-4" />
            </Button>
            <Button
              type="button"
              size="icon"
              onClick={() => void handleNewChat()}
              disabled={creating}
              aria-label={t("newChat")}
            >
              <MessageSquarePlusIcon className="size-4" />
            </Button>
          </div>
        </div>

        {isClosed && (
          <p className="bg-muted text-muted-foreground mx-6 mb-2 rounded-lg px-3 py-2 text-xs">
            {t("closedNote")}
          </p>
        )}

        <ChatMessageList
          messages={messages}
          namespace="admin.productSearch"
          onSelectProduct={setSelectedProduct}
          onFindSimilar={handleFindSimilar}
          onRetry={retry}
          onDebugOpen={setDebugTarget}
          loading={loadingNode}
          empty={emptyNode}
        />

        <ChatComposer
          key={activeId ?? "none"}
          status={status}
          canSend={canSend}
          isClosed={isClosed}
          onSend={sendMessage}
        />

        <ProductViewDialog {...productViewProps} />
      </div>

      <DebugDialog debug={debugTarget} onClose={() => setDebugTarget(null)} />

      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) {
            setDeleteTarget(null);
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogMedia>
              <Trash2Icon className="text-destructive" />
            </AlertDialogMedia>
            <AlertDialogTitle>{t("deleteChat")}</AlertDialogTitle>
            <AlertDialogDescription>{t("deleteConfirm")}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{commonT("cancel")}</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => void handleDelete(deleteTarget)}
            >
              {commonT("delete")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
