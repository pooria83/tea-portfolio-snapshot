"use client";

import { useCallback, useState } from "react";

export interface UsePaginationTable {
  skip: number;
  page: number;
  pageSize: number;
  next: () => void;
  previous: () => void;
  reset: () => void;
}

export function usePaginationTable(pageSize: number): UsePaginationTable {
  const [skip, setSkip] = useState(0);

  const next = useCallback(() => {
    setSkip((current) => current + pageSize);
  }, [pageSize]);

  const previous = useCallback(() => {
    setSkip((current) => Math.max(0, current - pageSize));
  }, [pageSize]);

  const reset = useCallback(() => {
    setSkip(0);
  }, []);

  return { skip, page: Math.floor(skip / pageSize) + 1, pageSize, next, previous, reset };
}
