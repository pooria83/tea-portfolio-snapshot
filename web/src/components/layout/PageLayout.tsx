"use client";

import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

interface PageLayoutProps {
  children: ReactNode;
  variant?: "wide" | "narrow";
  className?: string;
}

export function PageLayout({ children, variant = "wide", className }: PageLayoutProps) {
  if (variant === "narrow") {
    return <div className={cn("mx-auto max-w-2xl space-y-6", className)}>{children}</div>;
  }
  return <div className={cn("space-y-6", className)}>{children}</div>;
}
