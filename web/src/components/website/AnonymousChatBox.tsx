"use client";

import { useCallback, useEffect, useMemo, useState, useSyncExternalStore } from "react";
import { useLocale, useTranslations } from "next-intl";
import { ArrowLeftIcon } from "lucide-react";
import Image from "next/image";

import { useGetAnonymousChatSessionMutation } from "@/store/api/anonymousApi";
import { useChat } from "@/hooks/useChat";
import { useCloseOnBack } from "@/hooks/useCloseOnBack";
import { ChatInput } from "@/components/chat/ChatInput";
import { ChatMessageList, ChatMessageListLoading } from "@/components/chat/ChatMessageList";
import { DebugDialog } from "@/components/chat/DebugDialog";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { ProductViewDialog } from "@/components/product/ProductViewDialog";
import { localeValue } from "@/lib/locale";
import type { ChatMessage, ChatProduct } from "@/types/api";

const subscribe = () => () => {};

function AnonComposer({
  canSend,
  disabled,
  sendLabel,
  placeholder,
  className,
  onSend,
}: {
  canSend: boolean;
  disabled: boolean;
  sendLabel: string;
  placeholder: string;
  className: string;
  onSend: (content: string) => void;
}) {
  const [query, setQuery] = useState("");

  const submitQuery = () => {
    const content = query.trim();
    if (!content || !canSend) {
      return;
    }
    setQuery("");
    onSend(content);
  };

  return (
    <ChatInput
      value={query}
      onChange={setQuery}
      onSubmit={submitQuery}
      sendLabel={sendLabel}
      disabled={disabled}
      inputPlaceholder={placeholder}
      className={className}
    />
  );
}

export function AnonymousChatBox() {
  const t = useTranslations("website.chat");
  const locale = useLocale();
  const [session, setSession] = useState<{ token: string; conversationId: string } | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [debugTarget, setDebugTarget] = useState<ChatMessage["debug"]>(null);
  const [selectedProduct, setSelectedProduct] = useState<ChatProduct | null>(null);
  const mounted = useSyncExternalStore(
    subscribe,
    () => true,
    () => false,
  );

  const closeChat = useCallback(() => setExpanded(false), []);

  useCloseOnBack(expanded, closeChat, "anonymous-chat");

  const [getSession, { isLoading: sessionLoading }] = useGetAnonymousChatSessionMutation();

  const { messages, status, canSend, streaming, sendMessage, sendSimilar, retry } = useChat({
    conversationId: session?.conversationId ?? null,
    tokenOverride: session?.token ?? null,
  });

  useEffect(() => {
    let cancelled = false;

    async function createSession() {
      try {
        const result = await getSession({ locale }).unwrap();
        if (!cancelled) {
          setSession({
            token: result.token,
            conversationId: result.conversation.id,
          });
        }
      } catch (error) {
        console.warn("anonymous_chat_session_failed", error);
      }
    }

    void createSession();
    return () => {
      cancelled = true;
    };
  }, [getSession, locale]);

  const handleSubmit = useCallback(
    (content: string) => {
      setExpanded(true);
      sendMessage(content);
    },
    [sendMessage],
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

  const inputDisabled = !mounted || !session || !canSend;

  let sendLabel: string;
  if (status === "open") {
    sendLabel = t("send");
  } else if (status === "connecting") {
    sendLabel = t("connecting");
  } else {
    sendLabel = t("reconnecting");
  }

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
    () =>
      sessionLoading && !session ? <ChatMessageListLoading label={t("connecting")} /> : undefined,
    [sessionLoading, session, t],
  );

  const emptyNode = useMemo(
    () =>
      !sessionLoading && session && messages.length === 0 && !streaming ? (
        <div className="text-muted-foreground flex flex-1 items-center justify-center text-sm">
          {t("placeholder")}
        </div>
      ) : undefined,
    [sessionLoading, session, messages.length, streaming, t],
  );

  const chatContent = (
    <div className="flex min-h-0 flex-1 flex-col">
      <ChatMessageList
        messages={messages}
        namespace="website.chat"
        onSelectProduct={setSelectedProduct}
        onFindSimilar={handleFindSimilar}
        onRetry={retry}
        onDebugOpen={setDebugTarget}
        loading={loadingNode}
        empty={emptyNode}
      />

      <AnonComposer
        canSend={canSend}
        disabled={inputDisabled}
        sendLabel={sendLabel}
        placeholder={t("inputPlaceholder")}
        onSend={handleSubmit}
        className="shrink-0 border-t px-6 py-4"
      />
    </div>
  );

  return (
    <>
      <section className="border-border bg-card mx-auto w-full max-w-[800px] rounded-2xl border shadow-sm">
        <AnonComposer
          canSend={canSend}
          disabled={inputDisabled}
          sendLabel={sendLabel}
          placeholder={t("inputPlaceholder")}
          onSend={handleSubmit}
          className="p-2"
        />
      </section>

      <Sheet open={expanded} onOpenChange={setExpanded}>
        <SheetContent
          side="bottom"
          className="inset-0 w-full rounded-none border-0 data-[side=bottom]:h-full"
        >
          <div className="border-border flex items-center justify-center border-b">
            <Button
              onClick={closeChat}
              className="border-border h-full rounded-none border-r px-4"
              aria-label={t("back")}
            >
              <ArrowLeftIcon className="size-4" />
              {t("back")}
            </Button>
            <div className="flex flex-1 items-center justify-center py-2">
              <Image
                src="/logo-wide.svg"
                alt="AskTea.ai"
                width={300}
                height={48}
                className="h-[48px] w-auto max-w-sm"
              />
            </div>
          </div>
          {chatContent}
        </SheetContent>
      </Sheet>

      <ProductViewDialog {...productViewProps} />
      <DebugDialog debug={debugTarget} onClose={() => setDebugTarget(null)} />
    </>
  );
}
