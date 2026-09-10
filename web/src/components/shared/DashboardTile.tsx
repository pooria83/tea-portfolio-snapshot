"use client";

import type { ReactNode } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/routing";
import { cn } from "@/lib/utils";

interface DashboardTileProps {
  href: string;
  icon: ReactNode;
  label: string;
  description?: string;
  value?: string | number;
  subtext?: string;
  className?: string;
  children?: ReactNode;
}

export function DashboardTile({
  href,
  icon,
  label,
  description,
  value,
  subtext,
  className,
  children,
}: DashboardTileProps) {
  const t = useTranslations("dashboard");

  return (
    <Link
      href={href}
      className={cn(
        "group flex h-full flex-col rounded-2xl p-6 text-white shadow-lg transition-all duration-200 hover:scale-[1.02] hover:shadow-xl",
        className,
      )}
    >
      <div className="inline-flex self-start rounded-xl bg-white/20 p-2.5 backdrop-blur-sm">
        {icon}
      </div>
      {value == null ? (
        <p className="mt-4 truncate text-2xl font-bold text-white/90">{label}</p>
      ) : (
        <div className="mt-4 flex min-w-0 items-baseline gap-3">
          <p className="text-4xl font-bold tabular-nums">{value}</p>
          <p className="truncate text-4xl font-bold text-white/80">{label}</p>
        </div>
      )}
      {description && <p className="mt-1 text-sm text-white/60">{description}</p>}
      {children && <div className="mt-4 space-y-1">{children}</div>}
      {subtext && <p className="mt-auto pt-2 text-xs text-white/60">{subtext}</p>}
      {subtext == null && children == null && <div className="flex-1" />}
      {children != null && (
        <div className="mt-4 text-sm font-medium text-white/80 opacity-0 transition-opacity group-hover:opacity-100">
          {t("viewDetails")} →
        </div>
      )}
    </Link>
  );
}
