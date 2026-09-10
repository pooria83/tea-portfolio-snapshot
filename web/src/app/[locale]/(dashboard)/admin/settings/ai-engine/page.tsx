"use client";

import { startTransition, useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { extractApiError } from "@/lib/api";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
import { toast } from "sonner";
import {
  useGetEmbedModelsQuery,
  useGetSystemSettingsQuery,
  useEmbedTextMutation,
  useUpdateSystemSettingMutation,
} from "@/store/api/adminApi";
import type { EmbedTextResponse } from "@/types/api";

interface EmbeddingConfig {
  provider?: string;
  model?: string;
  base_url?: string;
  need_api_key?: boolean;
  api_key_encrypted?: boolean;
  api_key?: string;
}

function parseEmbeddingProvider(raw: string): EmbeddingConfig {
  if (!raw.startsWith("{")) {
    return { provider: raw };
  }
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as EmbeddingConfig;
    }
  } catch (error) {
    console.error("invalid_embedding_provider_json", error);
  }
  return { provider: raw };
}

export default function AIEngineSettingsPage() {
  const t = useTranslations("settings.aiEngine");
  const commonT = useTranslations("common");
  const { data: settings, isLoading } = useGetSystemSettingsQuery();
  const { data: embedModels, isLoading: modelsLoading } = useGetEmbedModelsQuery();
  const [updateSetting, { isLoading: saving }] = useUpdateSystemSettingMutation();

  const currentConf = useMemo(
    () =>
      parseEmbeddingProvider(settings?.find((s) => s.key === "embedding_provider")?.value ?? ""),
    [settings],
  );
  const currentTunnelUrl = useMemo(
    () => settings?.find((s) => s.key === "tei_tunnel_url")?.value ?? "",
    [settings],
  );

  const [selectedMode, setSelectedMode] = useState(currentConf.provider || "sentence_transformer");
  const [tunnelUrl, setTunnelUrl] = useState(currentTunnelUrl);
  const [selectedModel, setSelectedModel] = useState(currentConf.model || "");
  const [needApiKey, setNeedApiKey] = useState(Boolean(currentConf.need_api_key));
  const [apiKey, setApiKey] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [testText, setTestText] = useState("");
  const [testResult, setTestResult] = useState<EmbedTextResponse | null>(null);
  const [copied, setCopied] = useState(false);
  const [embedText, { isLoading: embedding }] = useEmbedTextMutation();

  const hasStoredKey = useMemo(
    () => Boolean(currentConf.api_key_encrypted && currentConf.api_key),
    [currentConf],
  );

  const [syncedConfigKey, setSyncedConfigKey] = useState<string | null>(null);
  const configKey = `${currentConf.provider ?? ""}|${currentConf.model ?? ""}|${
    currentConf.need_api_key ? "1" : "0"
  }|${currentTunnelUrl}`;
  useEffect(() => {
    if (isLoading || configKey === syncedConfigKey) {
      return;
    }
    startTransition(() => {
      setSyncedConfigKey(configKey);
      setSelectedMode(currentConf.provider || "sentence_transformer");
      setTunnelUrl(currentTunnelUrl);
      setSelectedModel(currentConf.model || "");
      setNeedApiKey(Boolean(currentConf.need_api_key));
      setApiKey("");
    });
  }, [isLoading, configKey, syncedConfigKey, currentConf, currentTunnelUrl]);

  const providerLabel = (value: string) => {
    const labels: Record<string, string> = {
      sentence_transformer: t("sentenceTransformer"),
      tei: t("tei"),
      openrouter: t("openrouter"),
    };
    return labels[value] ?? value;
  };

  const handleUpdate = async () => {
    try {
      if (selectedMode === "tei") {
        if (!selectedModel) {
          toast.error(t("modelRequired"));
          return;
        }
        if (!tunnelUrl.trim()) {
          toast.error(t("tunnelUrlRequired"));
          return;
        }
        const key = apiKey.trim();
        if (needApiKey && !key && !hasStoredKey) {
          toast.error(t("apiKeyRequired"));
          return;
        }
        if (key.length > 0 && key.length < 5) {
          toast.error(t("apiKeyTooShort"));
          return;
        }
        const url = tunnelUrl.trim();
        const config: EmbeddingConfig = {
          provider: "tei",
          model: selectedModel,
          base_url: url,
          need_api_key: needApiKey,
        };
        if (key) {
          config.api_key = key;
        }
        await updateSetting({
          key: "embedding_provider",
          value: JSON.stringify(config),
        }).unwrap();
        await updateSetting({ key: "tei_tunnel_url", value: url }).unwrap();
      } else {
        await updateSetting({ key: "embedding_provider", value: selectedMode }).unwrap();
      }
      toast.success(t("saved"));
      setDialogOpen(false);
      setApiKey("");
    } catch (error) {
      toast.error(extractApiError(error, commonT("error")));
    }
  };

  const handleEmbedTest = async () => {
    try {
      const result = await embedText({ text: testText }).unwrap();
      setTestResult(result);
      toast.success(t("embeddingSuccess"));
    } catch (error) {
      toast.error(extractApiError(error, commonT("error")));
    }
  };

  const handleCopyVector = async () => {
    try {
      if (!testResult) return;
      await navigator.clipboard.writeText(`[${testResult.embedding.join(", ")}]`);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error("clipboard_copy_failed", error);
      toast.error(commonT("error"));
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
          <CardTitle>{t("currentConfig")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <p className="text-lg font-medium">
            {currentConf.provider ? providerLabel(currentConf.provider) : "None"}
          </p>
          {currentConf.provider === "tei" && (
            <>
              {currentConf.model && (
                <p className="text-muted-foreground text-sm">{currentConf.model}</p>
              )}
              {currentTunnelUrl && (
                <p className="text-muted-foreground text-sm break-all">{currentTunnelUrl}</p>
              )}
              <p className="text-muted-foreground text-sm">
                {currentConf.need_api_key ? t("requiresApiKey") : t("noApiKeyRequired")}
              </p>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("updateTo")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Select value={selectedMode} onValueChange={(v) => v && setSelectedMode(v)}>
              <SelectTrigger className="w-full max-w-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="sentence_transformer">{t("sentenceTransformer")}</SelectItem>
                <SelectItem value="tei">{t("tei")}</SelectItem>
                <SelectItem value="openrouter">{t("openrouter")}</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {selectedMode === "tei" && (
            <div className="max-w-md space-y-4">
              <div className="space-y-2">
                <Label>{t("model")}</Label>
                <Select value={selectedModel} onValueChange={(v) => v && setSelectedModel(v)}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder={t("modelPlaceholder")} />
                  </SelectTrigger>
                  <SelectContent>
                    {modelsLoading ? (
                      <SelectItem value="__loading__" disabled>
                        {commonT("loading")}
                      </SelectItem>
                    ) : (
                      (embedModels ?? []).map((m) => (
                        <SelectItem key={m.id} value={m.model_name}>
                          {m.display_name}
                        </SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>{t("tunnelUrl")}</Label>
                <Input
                  value={tunnelUrl}
                  onChange={(e) => setTunnelUrl(e.target.value)}
                  placeholder="https://xxx.trycloudflare.com/v1"
                />
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between gap-4">
                  <Label>{t("needApiKey")}</Label>
                  <Switch checked={needApiKey} onCheckedChange={setNeedApiKey} />
                </div>
                {needApiKey && (
                  <div className="space-y-2">
                    <Input
                      type="password"
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      placeholder={t("apiKeyPlaceholder")}
                    />
                    {hasStoredKey && (
                      <p className="text-muted-foreground text-xs">{t("apiKeyStored")}</p>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          <AlertDialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <AlertDialogTrigger render={<Button disabled={saving} />}>
              {t("apply")}
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>{t("confirmTitle")}</AlertDialogTitle>
                <AlertDialogDescription>
                  {t("confirmDesc", { mode: providerLabel(selectedMode) })}
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>{commonT("cancel")}</AlertDialogCancel>
                <AlertDialogAction onClick={() => void handleUpdate()}>
                  {t("confirm")}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("embeddingTest")}</CardTitle>
          <CardDescription>{t("embeddingTestDesc")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Textarea
              value={testText}
              onChange={(e) => setTestText(e.target.value)}
              maxLength={1000}
              rows={4}
              className="w-full text-sm"
              placeholder={t("embeddingPlaceholder")}
            />
            <p className="text-muted-foreground text-xs">{testText.length}/1000</p>
          </div>

          <Button
            onClick={() => void handleEmbedTest()}
            disabled={embedding || testText.trim().length === 0}
          >
            {embedding ? t("embeddingLoading") : t("embeddingSubmit")}
          </Button>

          {testResult && (
            <div className="space-y-2">
              <p className="text-muted-foreground text-sm">
                {t("embeddingModel", { model: testResult.model })} ·{" "}
                {t("embeddingDims", { dims: testResult.dimensions })}
              </p>
              <Textarea
                readOnly
                rows={8}
                value={`[${testResult.embedding.join(", ")}]`}
                className="field-sizing-fixed max-h-48 min-h-48 w-full overflow-auto font-mono text-xs"
              />
              <Button className="w-full" variant="outline" onClick={() => void handleCopyVector()}>
                {copied ? t("embeddingCopied") : t("embeddingCopy")}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
