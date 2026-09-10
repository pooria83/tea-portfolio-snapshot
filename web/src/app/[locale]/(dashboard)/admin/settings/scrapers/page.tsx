"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { extractApiError, extractTranslationKey } from "@/lib/api";
import {
  useClearScraperHeaderMutation,
  useGetScraperHeadersQuery,
  useUpdateScraperHeaderMutation,
} from "@/store/api/adminApi";

export default function ScrapersSettingsPage() {
  const t = useTranslations("settings.scrapers");
  const commonT = useTranslations("common");
  const errorsT = useTranslations("errors");
  const { data: headers, isLoading } = useGetScraperHeadersQuery();
  const [updateHeader, { isLoading: saving }] = useUpdateScraperHeaderMutation();
  const [clearHeader, { isLoading: clearing }] = useClearScraperHeaderMutation();
  const [drafts, setDrafts] = useState<Record<string, string>>({});

  const handleSave = async (name: string) => {
    const header = drafts[name] ?? "";
    try {
      await updateHeader({ name, header }).unwrap();
      toast.success(t("saved"));
    } catch (error) {
      const key = extractTranslationKey(error);
      toast.error(key ? errorsT(key) : extractApiError(error, commonT("error")));
    }
  };

  const handleClear = async (name: string) => {
    try {
      await clearHeader(name).unwrap();
      toast.success(t("cleared"));
    } catch (error) {
      const key = extractTranslationKey(error);
      toast.error(key ? errorsT(key) : extractApiError(error, commonT("error")));
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

      {!headers || headers.length === 0 ? (
        <Card>
          <CardContent className="p-6">
            <p className="text-muted-foreground text-sm">{t("noScrapers")}</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-6">
          {headers.map((item) => (
            <Card key={item.id}>
              <CardHeader>
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <CardTitle className="font-mono">{item.name}</CardTitle>
                    {item.status === "error" ? (
                      <Badge variant="destructive">{t("statusError")}</Badge>
                    ) : (
                      <Badge variant={item.header ? "default" : "secondary"}>
                        {item.header ? t("statusReady") : t("statusNotConfigured")}
                      </Badge>
                    )}
                  </div>
                </div>
                {item.error_message ? (
                  <CardDescription className="text-destructive">
                    {item.error_message}
                  </CardDescription>
                ) : (
                  <CardDescription>{t("headerHint")}</CardDescription>
                )}
              </CardHeader>
              <CardContent className="space-y-4">
                <Textarea
                  className="font-mono text-xs"
                  rows={12}
                  value={drafts[item.name] ?? item.header ?? ""}
                  onChange={(event) =>
                    setDrafts((prev) => ({ ...prev, [item.name]: event.target.value }))
                  }
                  placeholder={t("headerPlaceholder")}
                />
                <div className="flex items-center gap-2">
                  <Button onClick={() => handleSave(item.name)} disabled={saving}>
                    {t("save")}
                  </Button>
                  <AlertDialog>
                    <AlertDialogTrigger render={<Button variant="outline" disabled={clearing} />}>
                      {t("clear")}
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>{t("clearConfirmTitle")}</AlertDialogTitle>
                        <AlertDialogDescription>{t("clearConfirmDesc")}</AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>{t("cancel")}</AlertDialogCancel>
                        <AlertDialogAction onClick={() => handleClear(item.name)}>
                          {t("clear")}
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
