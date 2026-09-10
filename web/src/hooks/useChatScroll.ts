"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const NEAR_BOTTOM_PX = 80;

interface UseChatScrollOptions {
  /** Messages rendered inside the container — length/content changes drive autoscroll. */
  messages: unknown[];
}

export function useChatScroll({ messages }: UseChatScrollOptions) {
  const [container, setContainer] = useState<HTMLDivElement | null>(null);
  const [nearBottom, setNearBottom] = useState(true);
  const lastMessageIdRef = useRef<unknown>(null);
  const nearBottomRef = useRef(true);
  const scrollRafRef = useRef<number | null>(null);

  const containerRef = useCallback((node: HTMLDivElement | null) => {
    setContainer(node);
  }, []);

  const scheduleScrollToBottom = useCallback((node: HTMLDivElement) => {
    if (typeof requestAnimationFrame !== "function") {
      node.scrollTo({ top: node.scrollHeight });
      return;
    }
    if (scrollRafRef.current !== null) {
      cancelAnimationFrame(scrollRafRef.current);
    }
    scrollRafRef.current = requestAnimationFrame(() => {
      scrollRafRef.current = null;
      node.scrollTo({ top: node.scrollHeight });
    });
  }, []);

  const cancelScrollRaf = useCallback(() => {
    if (scrollRafRef.current !== null) {
      cancelAnimationFrame(scrollRafRef.current);
      scrollRafRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!container) {
      return;
    }
    const update = () => {
      const distance = container.scrollHeight - container.scrollTop - container.clientHeight;
      setNearBottom(distance <= NEAR_BOTTOM_PX);
    };
    let rafToken = 0;
    let rafId: number | null = null;
    const handleScroll = () => {
      const token = rafToken + 1;
      rafToken = token;
      if (rafId !== null) {
        cancelAnimationFrame(rafId);
      }
      rafId = requestAnimationFrame(() => {
        rafId = null;
        if (rafToken === token) {
          update();
        }
      });
    };
    container.addEventListener("scroll", handleScroll, { passive: true });
    update();
    return () => {
      container.removeEventListener("scroll", handleScroll);
      if (rafId !== null) {
        cancelAnimationFrame(rafId);
      }
      cancelScrollRaf();
    };
  }, [container, cancelScrollRaf]);

  const jumpToBottom = useCallback(() => {
    if (!container || typeof container.scrollTo !== "function") {
      return;
    }
    cancelScrollRaf();
    container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
  }, [container, cancelScrollRaf]);

  useEffect(() => {
    nearBottomRef.current = nearBottom;
  }, [nearBottom]);

  const lastMessage = messages.at(-1) as { id?: unknown } | undefined;
  const lastMessageId = lastMessage?.id;

  useEffect(() => {
    if (!container || typeof container.scrollTo !== "function") {
      return;
    }
    const isNewTurn = lastMessageId !== lastMessageIdRef.current;
    lastMessageIdRef.current = lastMessageId;
    if (!isNewTurn && !nearBottomRef.current) {
      return;
    }
    scheduleScrollToBottom(container);
  }, [container, lastMessageId, messages, nearBottom, scheduleScrollToBottom]);

  return { containerRef, nearBottom, jumpToBottom };
}
