"use client";

import { useMemo } from "react";
import { useTranslations } from "next-intl";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";
import { extractApiError } from "@/lib/api";
import { useGetSystemSettingsQuery, useUpdateSystemSettingMutation } from "@/store/api/adminApi";

export default function SystemSettingsPage() {
  const t = useTranslations("settings.system");
  const commonT = useTranslations("common");
  const { data: settings, isLoading } = useGetSystemSettingsQuery();
  const [updateSetting, { isLoading: saving }] = useUpdateSystemSettingMutation();

  const cronSetting = useMemo(
    () => settings?.find((s) => s.key === "product_ai_generation_cron"),
    [settings],
  );
  const cronEnabled = cronSetting?.value === "true";

  const handleToggleCron = async (checked: boolean) => {
    try {
      await updateSetting({
        key: "product_ai_generation_cron",
        value: checked ? "true" : "false",
      }).unwrap();
      toast.success(t("saved"));
    } catch (error) {
      toast.error(extractApiError(error, commonT("error")));
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-12">
        <p className="text-muted-foreground">{commonT("loading")}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{t("title")}</h1>
        <p className="text-muted-foreground text-sm">{t("description")}</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t("cron")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between rounded-lg border p-4">
            <div className="space-y-1">
              <p className="text-sm font-medium">{t("productAiGenerationCron")}</p>
              <p className="text-muted-foreground text-sm">{t("productAiGenerationCronDesc")}</p>
            </div>
            <Switch checked={cronEnabled} onCheckedChange={handleToggleCron} disabled={saving} />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
