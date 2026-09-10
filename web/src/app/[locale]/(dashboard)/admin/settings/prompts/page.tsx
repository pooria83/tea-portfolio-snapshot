"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { extractApiError } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { useGetPromptTemplatesQuery, useUpdatePromptTemplatesMutation } from "@/store/api/adminApi";
import type { PromptTemplateResponse } from "@/types/llm";

const PROMPT_KEYS: { key: keyof PromptTemplateResponse; labelKey: string; descKey: string }[] = [
  { key: "pre_prompt", labelKey: "prePrompt", descKey: "prePromptDesc" },
  { key: "ending_prompt", labelKey: "endingPrompt", descKey: "endingPromptDesc" },
  { key: "chat_assistant", labelKey: "chatAssistant", descKey: "chatAssistantDesc" },
  { key: "parse_query", labelKey: "parseQuery", descKey: "parseQueryDesc" },
  { key: "summarize", labelKey: "summarize", descKey: "summarizeDesc" },
  { key: "title", labelKey: "titleLabel", descKey: "titleDesc" },
];

export default function PromptsPage() {
  const t = useTranslations("settings.prompts");
  const commonT = useTranslations("common");
  const { data, isLoading } = useGetPromptTemplatesQuery();
  const [updatePromptTemplates, { isLoading: saving }] = useUpdatePromptTemplatesMutation();
  const [values, setValues] = useState<Record<string, string>>({});

  useEffect(() => {
    if (data) {
      const next: Record<string, string> = {};
      for (const { key } of PROMPT_KEYS) {
        next[key] = data[key];
      }
      requestAnimationFrame(() => setValues(next));
    }
  }, [data]);

  const handleSave = async () => {
    try {
      await updatePromptTemplates(values).unwrap();
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

      {PROMPT_KEYS.map(({ key, labelKey, descKey }) => (
        <Card key={key}>
          <CardHeader>
            <CardTitle>{t(labelKey)}</CardTitle>
            <CardDescription>{t(descKey)}</CardDescription>
          </CardHeader>
          <CardContent>
            <Textarea
              value={values[key] ?? ""}
              onChange={(e) => setValues((prev) => ({ ...prev, [key]: e.target.value }))}
              rows={6}
              className="w-full font-mono text-sm"
            />
          </CardContent>
        </Card>
      ))}

      <Button onClick={handleSave} disabled={saving}>
        {saving ? t("saving") : t("save")}
      </Button>
    </div>
  );
}
