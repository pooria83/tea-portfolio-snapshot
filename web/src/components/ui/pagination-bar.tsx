"use client";

import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";

interface PaginationBarProps {
  page: number;
  totalPages: number;
  canPrevious: boolean;
  canNext: boolean;
  onPrevious: () => void;
  onNext: () => void;
  previousLabel: ReactNode;
  nextLabel: ReactNode;
  /** Custom page indicator; defaults to `Page {page} of {totalPages}`. */
  pageInfo?: ReactNode;
  /** Optional content on the left side (e.g. a total count). */
  leftContent?: ReactNode;
}

export function PaginationBar({
  page,
  totalPages,
  canPrevious,
  canNext,
  onPrevious,
  onNext,
  previousLabel,
  nextLabel,
  pageInfo,
  leftContent,
}: PaginationBarProps) {
  return (
    <div className="flex items-center justify-between">
      <div className="text-muted-foreground text-sm">
        {leftContent ?? pageInfo ?? `Page ${page} of ${totalPages}`}
      </div>
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" disabled={!canPrevious} onClick={onPrevious}>
          {previousLabel}
        </Button>
        <Button variant="outline" size="sm" disabled={!canNext} onClick={onNext}>
          {nextLabel}
        </Button>
      </div>
    </div>
  );
}
