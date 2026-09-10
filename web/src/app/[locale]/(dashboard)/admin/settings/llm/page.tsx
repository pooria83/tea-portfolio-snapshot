"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import {
  useGetLLMModelsQuery,
  useAddLLMApiKeyMutation,
  useToggleLLMApiKeyMutation,
  useDeleteLLMApiKeyMutation,
  useGetLLMSettingsQuery,
  useUpdateLLMSettingsMutation,
} from "@/store/api/adminApi";
import { extractApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { HiOutlinePlus, HiOutlineTrash } from "react-icons/hi";
import type { LLMModelItem } from "@/types/api";

function ApiKeyCard({
  keyItem,
  onToggle,
  onDelete,
}: {
  keyItem: { id: string; name?: string | null; is_active: boolean; masked_key: string };
  onToggle: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const t = useTranslations("settings.llm");
  const commonT = useTranslations("common");

  return (
    <div className="flex items-center justify-between rounded-lg border p-3">
      <div className="flex items-center gap-3">
        <Switch
          checked={keyItem.is_active}
          onCheckedChange={() => onToggle(keyItem.id)}
          aria-label={t("toggleKey")}
        />
        <div>
          {keyItem.name && <p className="text-sm leading-tight font-medium">{keyItem.name}</p>}
          <div className="flex items-center gap-2">
            <code className="bg-muted rounded px-2 py-0.5 font-mono text-sm">
              {keyItem.masked_key}
            </code>
            <span
              className={`text-xs ${
                keyItem.is_active ? "text-green-600" : "text-muted-foreground"
              }`}
            >
              {keyItem.is_active ? t("active") : t("inactive")}
            </span>
          </div>
        </div>
      </div>
      <AlertDialog>
        <AlertDialogTrigger render={<Button variant="ghost" size="sm" />}>
          <HiOutlineTrash className="text-destructive h-4 w-4" />
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("deleteKey")}</AlertDialogTitle>
            <AlertDialogDescription>{t("confirmDelete")}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{commonT("cancel")}</AlertDialogCancel>
            <AlertDialogAction onClick={() => onDelete(keyItem.id)}>
              {commonT("delete")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function ModelCard({
  model,
  onToggle,
  onDelete,
}: {
  model: LLMModelItem;
  onToggle: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const t = useTranslations("settings.llm");

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">{model.model}</CardTitle>
        <CardDescription>{model.provider}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {model.api_keys.length === 0 ? (
          <p className="text-muted-foreground text-sm">{t("noKeys")}</p>
        ) : (
          model.api_keys.map((keyItem) => (
            <ApiKeyCard
              key={keyItem.id}
              keyItem={keyItem}
              onToggle={onToggle}
              onDelete={onDelete}
            />
          ))
        )}
      </CardContent>
    </Card>
  );
}

function AddKeyDialog({ models }: { models: LLMModelItem[] }) {
  const t = useTranslations("settings.llm");
  const commonT = useTranslations("common");
  const [open, setOpen] = useState(false);
  const [modelId, setModelId] = useState("");
  const [keyName, setKeyName] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [addKey, { isLoading }] = useAddLLMApiKeyMutation();

  const selectedModel = modelId ? models.find((m) => m.id === modelId) : null;

  const handleSubmit = async () => {
    if (!modelId || !apiKey.trim()) return;
    try {
      await addKey({
        model_id: modelId,
        api_key: apiKey.trim(),
        ...(keyName.trim() ? { name: keyName.trim() } : {}),
      }).unwrap();
      navigator.clipboard
        .writeText(apiKey.trim())
        .catch(() => console.warn("clipboard write failed"));
      toast.success(t("keyAdded"), {
        action: {
          label: t("copyKey"),
          onClick: () =>
            navigator.clipboard
              .writeText(apiKey.trim())
              .catch(() => console.warn("clipboard write failed")),
        },
      });
      setApiKey("");
      setModelId("");
      setKeyName("");
      setOpen(false);
    } catch (error) {
      toast.error(extractApiError(error, t("errorLoading")));
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <Button>
            <HiOutlinePlus className="mr-2 h-4 w-4" />
            {t("addKey")}
          </Button>
        }
      />
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t("addKey")}</DialogTitle>
          <DialogDescription>{t("description")}</DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label>{t("model")}</Label>
            <Select value={modelId} onValueChange={(value) => value && setModelId(value)}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder={t("model")}>
                  {selectedModel ? `${selectedModel.provider} — ${selectedModel.model}` : null}
                </SelectValue>
              </SelectTrigger>
              <SelectContent className="w-(--anchor-width)">
                {models.map((m) => (
                  <SelectItem key={m.id} value={m.id}>
                    {m.provider} — {m.model}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>{t("keyNameLabel")}</Label>
            <Input
              value={keyName}
              onChange={(e) => setKeyName(e.target.value)}
              placeholder={t("keyNamePlaceholder")}
            />
          </div>
          <div className="space-y-2">
            <Label>{t("apiKeyLabel")}</Label>
            <Input
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={t("apiKeyPlaceholder")}
              type="password"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            {commonT("cancel")}
          </Button>
          <Button onClick={handleSubmit} disabled={isLoading || !modelId || !apiKey.trim()}>
            {t("addKey")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ModelSelectSection({
  title,
  description,
  models,
  selectedModelId,
  onChange,
  onSave,
  saving,
}: {
  title: string;
  description: string;
  models: LLMModelItem[];
  selectedModelId: string | null;
  onChange: (id: string | null) => void;
  onSave: () => void;
  saving: boolean;
}) {
  const commonT = useTranslations("common");

  const modelsWithActiveKeys = useMemo(
    () => models.filter((m) => m.api_keys.some((k) => k.is_active)),
    [models],
  );
  const selectedModel = useMemo(
    () => (selectedModelId ? modelsWithActiveKeys.find((m) => m.id === selectedModelId) : null),
    [selectedModelId, modelsWithActiveKeys],
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Select value={selectedModelId ?? ""} onValueChange={(value) => onChange(value || null)}>
          <SelectTrigger className="w-full">
            <SelectValue placeholder={title}>
              {selectedModel ? `${selectedModel.provider} — ${selectedModel.model}` : null}
            </SelectValue>
          </SelectTrigger>
          <SelectContent className="w-(--anchor-width)">
            {modelsWithActiveKeys.length === 0 && (
              <p className="text-muted-foreground p-2 text-sm">
                {title} — {description}
              </p>
            )}
            {modelsWithActiveKeys.map((m) => (
              <SelectItem key={m.id} value={m.id}>
                {m.provider} — {m.model}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button onClick={onSave} disabled={saving}>
          {commonT("save")}
        </Button>
      </CardContent>
    </Card>
  );
}

export default function LLMSettingsPage() {
  const t = useTranslations("settings.llm");
  const commonT = useTranslations("common");
  const { data: models, isLoading, isError, refetch } = useGetLLMModelsQuery();
  const { data: settings, isLoading: isSettingsLoading } = useGetLLMSettingsQuery();
  const [updateSettings, { isLoading: isUpdating }] = useUpdateLLMSettingsMutation();
  const [toggleKey] = useToggleLLMApiKeyMutation();
  const [deleteKey] = useDeleteLLMApiKeyMutation();

  const [defaultLlmModelId, setDefaultLlmModelId] = useState<string | null>(null);
  const [userCommModelId, setUserCommModelId] = useState<string | null>(null);

  useEffect(() => {
    if (settings) {
      requestAnimationFrame(() => {
        setDefaultLlmModelId(settings.default_llm_model_id);
        setUserCommModelId(settings.user_comm_model_id);
      });
    }
  }, [settings]);

  const handleToggle = async (keyId: string) => {
    try {
      await toggleKey(keyId).unwrap();
      toast.success(t("keyToggled"));
    } catch (error) {
      toast.error(extractApiError(error, t("errorLoading")));
    }
  };

  const handleDelete = async (keyId: string) => {
    try {
      await deleteKey(keyId).unwrap();
      toast.success(t("keyDeleted"));
    } catch (error) {
      toast.error(extractApiError(error, t("errorLoading")));
    }
  };

  const handleSaveDefault = async () => {
    try {
      await updateSettings({ default_llm_model_id: defaultLlmModelId }).unwrap();
      toast.success(t("settingsSaved"));
    } catch {
      toast.error(t("errorLoading"));
    }
  };

  const handleSaveUserComm = async () => {
    try {
      await updateSettings({ user_comm_model_id: userCommModelId }).unwrap();
      toast.success(t("settingsSaved"));
    } catch (error) {
      toast.error(extractApiError(error, t("errorLoading")));
    }
  };

  const groupedByProvider = useMemo(
    () =>
      (models ?? []).reduce<Record<string, LLMModelItem[]>>(
        (acc, m) => {
          const group = acc[m.provider];
          if (group) {
            group.push(m);
          } else {
            acc[m.provider] = [m];
          }
          return acc;
        },
        {} as Record<string, LLMModelItem[]>,
      ),
    [models],
  );

  if (isLoading || isSettingsLoading) {
    return (
      <div className="flex items-center justify-center p-12">
        <p className="text-muted-foreground">{commonT("loading")}</p>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 p-12">
        <p className="text-destructive">{t("errorLoading")}</p>
        <Button variant="outline" onClick={refetch}>
          {commonT("retry")}
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{t("title")}</h1>
          <p className="text-muted-foreground text-sm">{t("description")}</p>
        </div>
        {models && models.length > 0 && <AddKeyDialog models={models} />}
      </div>

      {models && models.length > 0 && (
        <>
          <div className="grid gap-6 sm:grid-cols-2">
            <ModelSelectSection
              title={t("defaultModel")}
              description={t("defaultModelDesc")}
              models={models}
              selectedModelId={defaultLlmModelId}
              onChange={setDefaultLlmModelId}
              onSave={handleSaveDefault}
              saving={isUpdating}
            />
            <ModelSelectSection
              title={t("userCommModel")}
              description={t("userCommModelDesc")}
              models={models}
              selectedModelId={userCommModelId}
              onChange={setUserCommModelId}
              onSave={handleSaveUserComm}
              saving={isUpdating}
            />
          </div>
          {Object.entries(groupedByProvider).map(([provider, providerModels]) => (
            <section key={provider}>
              <h2 className="mb-4 text-xl font-semibold capitalize">{provider}</h2>
              <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                {providerModels.map((model) => (
                  <ModelCard
                    key={model.id}
                    model={model}
                    onToggle={handleToggle}
                    onDelete={handleDelete}
                  />
                ))}
              </div>
            </section>
          ))}
        </>
      )}

      {(!models || models.length === 0) && (
        <div className="flex flex-col items-center justify-center gap-4 rounded-lg border border-dashed p-12">
          <p className="text-muted-foreground">{t("noModels")}</p>
        </div>
      )}
    </div>
  );
}
