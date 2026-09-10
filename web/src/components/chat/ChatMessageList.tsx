"use client";

import { useTranslations } from "next-intl";
import { ArrowDownIcon, Loader2Icon } from "lucide-react";
import { memo, useMemo, type ReactNode } from "react";

import { AssistantBubble } from "@/components/chat/AssistantBubble";
import { CopyButton } from "@/components/chat/CopyButton";
import { DebugButton } from "@/components/chat/DebugButton";
import { Markdown } from "@/components/chat/Markdown";
import { ProductGrid } from "@/components/chat/ProductGrid";
import { Button } from "@/components/ui/button";
import { Bubble, BubbleContent } from "@/components/ui/bubble";
import { Message, MessageContent } from "@/components/ui/message";
import { useChatScroll } from "@/hooks/useChatScroll";
import { isChatErrorCode } from "@/lib/chat";
import { localeDirection } from "@/lib/locale";
import type { ChatViewMessage } from "@/lib/chatTypes";
import type { ChatProduct } from "@/types/api";

function StreamingDots() {
  return (
    <span className="flex items-center gap-1" aria-label="streaming" role="status">
      <span className="bg-foreground/60 size-1.5 animate-bounce rounded-full [animation-delay:-0.3s]" />
      <span className="bg-foreground/60 size-1.5 animate-bounce rounded-full [animation-delay:-0.15s]" />
      <span className="bg-foreground/60 size-1.5 animate-bounce rounded-full" />
    </span>
  );
}

function AssistantBody({
  message,
  failureText,
}: {
  message: ChatViewMessage;
  failureText: string;
}) {
  if (message.status === "streaming" && !message.content) {
    return <StreamingDots />;
  }
  if (message.status === "failed" || message.error) {
    return <BubbleContent className="text-muted-foreground italic">{failureText}</BubbleContent>;
  }
  return (
    <Markdown dir={message.locale ? localeDirection(message.locale) : "auto"}>
      {message.content}
    </Markdown>
  );
}

const messagePropsEqual = (
  prev: { message: ChatViewMessage; namespace: string; userMessage?: ChatViewMessage | null },
  next: { message: ChatViewMessage; namespace: string; userMessage?: ChatViewMessage | null },
) =>
  prev.message === next.message &&
  prev.namespace === next.namespace &&
  prev.userMessage === next.userMessage;

const UserMessageItem = memo(function UserMessageItem({
  message,
  namespace,
}: {
  message: ChatViewMessage;
  namespace: string;
}) {
  const t = useTranslations(namespace);

  if (message.kind === "similar") {
    if (message.status === "saved") {
      return null;
    }
    return (
      <Message align="end">
        <MessageContent>
          <p className="text-muted-foreground text-xs italic">
            {t("findingSimilar", { name: message.content })}
          </p>
        </MessageContent>
      </Message>
    );
  }

  return (
    <Message align="end">
      <MessageContent>
        <Bubble variant="default" align="end">
          <BubbleContent className="whitespace-pre-wrap" dir="auto">
            {message.content}
          </BubbleContent>
        </Bubble>
        <CopyButton text={message.content} label={t("copyMessage")} copiedLabel={t("copied")} />
      </MessageContent>
    </Message>
  );
}, messagePropsEqual);

const AssistantMessageItem = memo(function AssistantMessageItem({
  message,
  namespace,
  userMessage,
  onSelectProduct,
  onFindSimilar,
  onDebugOpen,
  onRetry,
}: {
  message: ChatViewMessage;
  namespace: string;
  userMessage?: ChatViewMessage | null;
  onSelectProduct: (product: ChatProduct) => void;
  onFindSimilar: (product: ChatProduct) => void;
  onDebugOpen: (debug: ChatViewMessage["debug"]) => void;
  onRetry: (message: ChatViewMessage) => void;
}) {
  const t = useTranslations(namespace);
  const errorsT = useTranslations("errors");
  const failureText =
    message.error && isChatErrorCode(message.error) ? errorsT(message.error) : t("error");
  const isErrorTurn =
    (message.error != null || message.searchContext?.intent === "error") &&
    message.status !== "pending" &&
    message.status !== "streaming";

  return (
    <Message align="start">
      <MessageContent className="gap-3">
        {message.products.length > 0 && (
          <ProductGrid
            products={message.products}
            onSelect={onSelectProduct}
            onFindSimilar={onFindSimilar}
            {...(message.locale ? { locale: message.locale } : {})}
          />
        )}
        <AssistantBubble
          intent={message.searchContext?.intent ?? (message.error ? "error" : undefined)}
        >
          <AssistantBody message={message} failureText={failureText} />
        </AssistantBubble>
        {isErrorTurn && userMessage && (
          <span className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => onRetry(userMessage)}
              aria-label={t("retry")}
            >
              {t("retry")}
            </Button>
          </span>
        )}
        {message.debug && (
          <DebugButton debug={message.debug} label={t("debug")} onOpen={onDebugOpen} />
        )}
      </MessageContent>
    </Message>
  );
}, messagePropsEqual);

export const ChatMessageList = memo(function ChatMessageList({
  messages,
  namespace,
  onSelectProduct,
  onFindSimilar,
  onRetry,
  onDebugOpen,
  loading,
  empty,
  className,
}: {
  messages: ChatViewMessage[];
  namespace: "admin.productSearch" | "website.chat";
  onSelectProduct: (product: ChatProduct) => void;
  onFindSimilar: (product: ChatProduct) => void;
  onRetry: (message: ChatViewMessage) => void;
  onDebugOpen: (debug: ChatViewMessage["debug"]) => void;
  /** Optional loading state rendered instead of the list (e.g. history fetch). */
  loading?: ReactNode;
  /** Optional empty state rendered when no messages are present. */
  empty?: ReactNode;
  className?: string;
}) {
  const t = useTranslations(namespace);
  const { containerRef, nearBottom, jumpToBottom } = useChatScroll({ messages });
  const userByPairId = useMemo(() => {
    const map = new Map<string, ChatViewMessage>();
    for (const message of messages) {
      if (message.role === "user" && !map.has(message.pairId)) {
        map.set(message.pairId, message);
      }
    }
    return map;
  }, [messages]);

  return (
    <div className="relative flex min-h-0 flex-1 flex-col">
      <div
        ref={containerRef}
        className={`flex min-h-0 flex-1 flex-col overflow-y-auto px-6 pb-4 ${className ?? ""}`}
      >
        <div className="mx-auto flex w-full max-w-[1024px] flex-col gap-4">
          {loading ?? null}

          {!loading && empty && messages.length === 0 ? empty : null}

          {messages.map((message) =>
            message.role === "user" ? (
              <UserMessageItem
                key={message.kind === "similar" ? message.pairId : message.id}
                message={message}
                namespace={namespace}
              />
            ) : (
              <AssistantMessageItem
                key={message.id}
                message={message}
                namespace={namespace}
                userMessage={userByPairId.get(message.pairId) ?? null}
                onSelectProduct={onSelectProduct}
                onFindSimilar={onFindSimilar}
                onDebugOpen={onDebugOpen}
                onRetry={onRetry}
              />
            ),
          )}
        </div>
      </div>

      {!nearBottom && messages.length > 0 && (
        <Button
          type="button"
          variant="outline"
          size="icon"
          onClick={jumpToBottom}
          aria-label={t("jumpToBottom")}
          className="absolute right-1/2 bottom-4 translate-x-1/2 rounded-full shadow-md"
        >
          <ArrowDownIcon className="size-4" />
        </Button>
      )}
    </div>
  );
});

export function ChatMessageListLoading({ label }: { label?: string }) {
  return (
    <div className="text-muted-foreground flex flex-1 items-center justify-center gap-2 text-sm">
      <Loader2Icon className="size-4 animate-spin" />
      {label}
    </div>
  );
}
