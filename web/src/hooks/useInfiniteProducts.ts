"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";
import type { PaginationMeta } from "@/types/api";

export interface PageResult<T> {
  items: T[];
  meta: PaginationMeta;
}

interface State<T> {
  items: T[];
  total: number;
  hasMore: boolean;
  isLoading: boolean;
  isLoadingMore: boolean;
}

type Action<T> =
  | { type: "reset" }
  | { type: "load_start" }
  | { type: "add_items"; items: T[]; total: number; hasMore: boolean }
  | { type: "finish_loading" };

const INITIAL_STATE: State<never> = {
  items: [],
  total: 0,
  hasMore: true,
  isLoading: true,
  isLoadingMore: false,
};

function reducer<T extends { id: string }>(state: State<T>, action: Action<T>): State<T> {
  switch (action.type) {
    case "reset": {
      return { ...INITIAL_STATE, items: [] };
    }
    case "load_start": {
      return { ...state, isLoadingMore: true };
    }
    case "add_items": {
      const existingIds = new Set(state.items.map((i) => i.id));
      const newItems = action.items.filter((i) => !existingIds.has(i.id));
      return {
        ...state,
        items: [...state.items, ...newItems],
        total: action.total,
        hasMore: action.hasMore,
      };
    }
    case "finish_loading": {
      return { ...state, isLoading: false, isLoadingMore: false };
    }
    default: {
      return state;
    }
  }
}

const DEFAULT_LIMIT = 20;

export function useInfiniteProducts<T extends { id: string }>(
  fetchPage: (params: { skip: number; limit: number }) => Promise<{ data?: PageResult<T> }>,
  deps: unknown[] = [],
) {
  const [state, dispatch] = useReducer(reducer<T>, INITIAL_STATE, () => ({ ...INITIAL_STATE }));
  const skipRef = useRef(0);
  const hasMoreRef = useRef(true);
  const loadingRef = useRef(false);
  const epochRef = useRef(0);
  const observerRef = useRef<IntersectionObserver | null>(null);
  const fetchPageRef = useRef(fetchPage);
  useEffect(() => {
    fetchPageRef.current = fetchPage;
  }, [fetchPage]);

  const loadMore = useCallback(async () => {
    if (loadingRef.current || !hasMoreRef.current) return;
    loadingRef.current = true;
    dispatch({ type: "load_start" });
    const skip = skipRef.current;
    const epoch = epochRef.current;
    try {
      const { data } = await fetchPageRef.current({ skip, limit: DEFAULT_LIMIT });
      if (data && epoch === epochRef.current) {
        const hasMore = data.meta.has_next;
        dispatch({
          type: "add_items",
          items: data.items,
          total: data.meta.total,
          hasMore,
        });
        hasMoreRef.current = hasMore;
        skipRef.current = skip + DEFAULT_LIMIT;
      }
    } catch (error) {
      console.error("Failed to load more items:", error);
    }
    loadingRef.current = false;
    dispatch({ type: "finish_loading" });
  }, [dispatch]);

  const refresh = useCallback(async () => {
    epochRef.current += 1;
    skipRef.current = 0;
    hasMoreRef.current = true;
    loadingRef.current = false;
    dispatch({ type: "reset" });
    await loadMore();
  }, [dispatch, loadMore]);

  const depsKey = JSON.stringify(deps);
  useEffect(() => {
    epochRef.current += 1;
    skipRef.current = 0;
    hasMoreRef.current = true;
    loadingRef.current = false;
    dispatch({ type: "reset" });
    void loadMore();
  }, [depsKey, dispatch, loadMore]);

  const sentinelRef = useCallback(
    (node: HTMLDivElement | null) => {
      if (observerRef.current) observerRef.current.disconnect();
      if (!node) return;
      observerRef.current = new IntersectionObserver(
        (entries) => {
          if (entries[0]?.isIntersecting && hasMoreRef.current && !loadingRef.current) {
            void loadMore();
          }
        },
        { rootMargin: "200px" },
      );
      observerRef.current.observe(node);
    },
    [loadMore],
  );

  return { ...state, sentinelRef, refresh } as const;
}
