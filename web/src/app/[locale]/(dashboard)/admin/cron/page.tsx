"use client";

import { useTranslations } from "next-intl";
import { useGetCronSummaryQuery } from "@/store/api/adminApi";
import { HiOutlineClipboardList, HiOutlineCube } from "react-icons/hi";
import { DashboardTile } from "@/components/shared/DashboardTile";

export default function CronHubPage() {
  const t = useTranslations("settings.cron");
  const { data: summary, isLoading } = useGetCronSummaryQuery();
  const iconSize = "size-6";

  return (
    <div>
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{t("hubTitle")}</h1>
        <p className="text-muted-foreground text-sm">{t("hubDescription")}</p>
      </div>

      {isLoading ? (
        <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="bg-muted rounded-2xl p-6">
            <div className="bg-muted-foreground/20 h-6 w-1/3 animate-pulse rounded" />
            <div className="bg-muted-foreground/20 mt-2 h-4 w-2/3 animate-pulse rounded" />
          </div>
          <div className="bg-muted rounded-2xl p-6">
            <div className="bg-muted-foreground/20 h-6 w-1/3 animate-pulse rounded" />
            <div className="bg-muted-foreground/20 mt-2 h-4 w-2/3 animate-pulse rounded" />
          </div>
        </div>
      ) : (
        <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
          <DashboardTile
            href="/admin/cron/llm-product-description"
            icon={<HiOutlineClipboardList className={iconSize} />}
            label={t("llmCron")}
            description={t("llmCronDesc")}
            className="bg-gradient-to-br from-blue-600 to-indigo-700"
          >
            <div className="flex gap-4 text-sm">
              <span>{t("pendingCount", { count: summary?.llm.pending ?? 0 })}</span>
              <span>{t("generatedCount", { count: summary?.llm.generated ?? 0 })}</span>
            </div>
          </DashboardTile>
          <DashboardTile
            href="/admin/cron/embeding-product"
            icon={<HiOutlineCube className={iconSize} />}
            label={t("embeddingCron")}
            description={t("embeddingCronDesc")}
            className="bg-gradient-to-br from-emerald-500 to-teal-700"
          />
        </div>
      )}
    </div>
  );
}
