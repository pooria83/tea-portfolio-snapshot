"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import { useRouter } from "@/i18n/routing";
import { extractApiError } from "@/lib/api";
import { PageLayout } from "@/components/layout/PageLayout";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  useGenerateProductDescriptionMutation,
  useGetStoreProductQuery,
  useUpdateStoreProductMutation,
} from "@/store/api/productApi";
import { useGetLLMModelsQuery } from "@/store/api/adminApi";
import { toast } from "sonner";
import { FiRefreshCw, FiClock, FiCheck, FiTerminal } from "react-icons/fi";
import type { LLMModelItem } from "@/types/api";

type PageState = "loading" | "done" | "saving" | "error";

export default function GenerateDescriptionPage() {
  const t = useTranslations("product");
  const params = useParams();
  const router = useRouter();
  const storeId = params.id as string;
  const productId = params.productId as string;

  const [pageState, setPageState] = useState<PageState>("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const [enText, setEnText] = useState("");
  const [arText, setArText] = useState("");
  const [showHistory, setShowHistory] = useState(false);
  const [showPrompt, setShowPrompt] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [currentModel, setCurrentModel] = useState<string | null>(null);
  const [history, setHistory] = useState<
    {
      description_en: string | null;
      description_ar: string | null;
      model: string | null;
      created_at: string;
    }[]
  >([]);

  const [triggerGenerate, { isLoading: isGenerating }] = useGenerateProductDescriptionMutation();
  const [updateProduct, { isLoading: isUpdating }] = useUpdateStoreProductMutation();
  const { data: product, isLoading: productLoading } = useGetStoreProductQuery({
    store_id: storeId,
    product_id: productId,
  });

  const { data: allModels } = useGetLLMModelsQuery();
  const modelsWithActiveKeys: LLMModelItem[] = (allModels ?? []).filter((m) =>
    m.api_keys.some((k) => k.is_active),
  );

  const versions = useMemo(() => product?.ai_description_versions ?? [], [product]);
  const [hydratedProductId, setHydratedProductId] = useState<string | null>(null);
  if (product && !productLoading && versions.length > 0 && hydratedProductId !== product.id) {
    setHydratedProductId(product.id);
    const latest = [...versions].toSorted(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    )[0];
    setEnText(latest?.description_en ?? product.ai_description_en ?? "");
    setArText(latest?.description_ar ?? product.ai_description_ar ?? "");
    setPrompt("");
    setCurrentModel(latest?.model ?? null);
    setHistory(versions);
    setPageState("done");
  }

  useEffect(() => {
    if (productLoading || !product) return;
    if (versions.length > 0) return;
    let cancelled = false;
    async function run() {
      setPageState("loading");
      setErrorMessage("");
      try {
        const result = await triggerGenerate({ store_id: storeId, product_id: productId }).unwrap();
        if (cancelled) return;
        setEnText(result.descriptions.en);
        setArText(result.descriptions.ar);
        setPrompt(result.prompt);
        setCurrentModel(result.model);
        setHistory(result.history);
        setPageState("done");
        toast.success(t("generateDescription.generated"));
      } catch {
        if (cancelled) return;
        setPageState("error");
        setErrorMessage(t("generateDescription.failed"));
      }
    }
    void run();
    return () => {
      cancelled = true;
    };
  }, [product, productLoading, versions, triggerGenerate, storeId, productId, t]);

  async function regenerate() {
    setPageState("loading");
    setErrorMessage("");
    try {
      const result = await triggerGenerate({
        store_id: storeId,
        product_id: productId,
        ...(currentModel ? { model: currentModel } : {}),
      }).unwrap();
      setEnText(result.descriptions.en);
      setArText(result.descriptions.ar);
      setPrompt(result.prompt);
      setCurrentModel(result.model);
      setHistory(result.history);
      setPageState("done");
      toast.success(t("generateDescription.generated"));
    } catch {
      setPageState("error");
      setErrorMessage(t("generateDescription.failed"));
    }
  }

  async function regenerateWithPrompt() {
    setPageState("loading");
    setErrorMessage("");
    try {
      const result = await triggerGenerate({
        store_id: storeId,
        product_id: productId,
        prompt,
        ...(currentModel ? { model: currentModel } : {}),
      }).unwrap();
      setEnText(result.descriptions.en);
      setArText(result.descriptions.ar);
      setPrompt(result.prompt);
      setCurrentModel(result.model);
      setHistory(result.history);
      setPageState("done");
      toast.success(t("generateDescription.generated"));
    } catch {
      setPageState("error");
      setErrorMessage(t("generateDescription.failed"));
    }
  }

  async function handleSave() {
    setPageState("saving");
    try {
      await updateProduct({
        store_id: storeId,
        product_id: productId,
        data: { ai_description_en: enText, ai_description_ar: arText },
      }).unwrap();
      toast.success(t("generateDescription.saved"));
      setPageState("done");
    } catch (error) {
      toast.error(extractApiError(error, t("error")));
      setPageState("done");
    }
  }

  function handleNext() {
    router.push("/seller/products");
  }

  return (
    <PageLayout variant="narrow" className="flex h-full flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{t("generateDescription.title")}</h1>
        <div className="flex items-center gap-2">
          {pageState === "done" && (
            <>
              <Button variant="outline" size="sm" onClick={() => setShowPrompt(!showPrompt)}>
                <FiTerminal className="mr-1.5 size-4" />
                {t("generateDescription.showPrompt")}
              </Button>
              <Button variant="outline" size="sm" onClick={() => setShowHistory(!showHistory)}>
                <FiClock className="mr-1.5 size-4" />
                {t("generateDescription.history")}
              </Button>
              <Button variant="outline" size="sm" onClick={regenerate} disabled={isGenerating}>
                <FiRefreshCw className={`mr-1.5 size-4 ${isGenerating ? "animate-spin" : ""}`} />
                {t("generateDescription.regenerate")}
              </Button>
            </>
          )}
        </div>
      </div>

      {pageState === "loading" && (
        <div className="flex flex-1 flex-col items-center justify-center gap-4">
          <Spinner className="size-10" />
          <p className="text-muted-foreground text-lg">{t("generateDescription.loading")}</p>
          <p className="text-muted-foreground text-sm">
            {t("generateDescription.loadingProgress")}
          </p>
        </div>
      )}

      {pageState === "done" && (
        <div className="flex flex-1 flex-col gap-6">
          {showPrompt && (
            <div className="space-y-2">
              <div className="space-y-2">
                <Label>{t("generateDescription.modelLabel")}</Label>
                <Select
                  value={currentModel ?? ""}
                  onValueChange={(value) => setCurrentModel(value || null)}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder={t("generateDescription.modelLabel")}>
                      {currentModel}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent className="w-(--anchor-width)">
                    {modelsWithActiveKeys.map((m) => (
                      <SelectItem key={m.id} value={m.model}>
                        {m.provider} — {m.model}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <h3 className="text-lg font-semibold">{t("generateDescription.promptLabel")}</h3>
              <Textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                rows={8}
                className="min-h-[200px] resize-y font-mono text-xs"
              />
              <Button
                variant="secondary"
                size="sm"
                className="w-full bg-emerald-600 text-white hover:bg-emerald-700"
                onClick={regenerateWithPrompt}
                disabled={isGenerating}
              >
                {isGenerating ? (
                  <Spinner className="mr-1.5 size-4" />
                ) : (
                  <FiRefreshCw className="mr-1.5 size-4" />
                )}
                {t("generateDescription.runEditedPrompt")}
              </Button>
            </div>
          )}

          <div className="flex flex-col gap-4">
            <div className="space-y-2">
              <h3 className="text-lg font-semibold">{t("generateDescription.descriptionEn")}</h3>
              <Textarea
                value={enText}
                onChange={(e) => setEnText(e.target.value)}
                rows={6}
                className="min-h-[160px] resize-y"
              />
            </div>
            <div className="space-y-2">
              <h3 className="text-lg font-semibold">{t("generateDescription.descriptionAr")}</h3>
              <Textarea
                value={arText}
                onChange={(e) => setArText(e.target.value)}
                rows={6}
                className="min-h-[160px] resize-y"
                dir="rtl"
              />
            </div>
          </div>

          <div className="flex items-center justify-between">
            <Button onClick={handleSave} disabled={isUpdating}>
              {isUpdating ? (
                <>{t("generateDescription.saving")}</>
              ) : (
                <>
                  <FiCheck className="mr-1.5 size-4" />
                  {t("generateDescription.saveChanges")}
                </>
              )}
            </Button>
            <Button variant="default" onClick={handleNext}>
              {t("generateDescription.next")}
            </Button>
          </div>
        </div>
      )}

      {pageState === "error" && (
        <div className="flex flex-1 flex-col items-center justify-center gap-4">
          <p className="text-destructive text-lg">{errorMessage}</p>
          <div className="flex gap-3">
            <Button onClick={regenerate} disabled={isGenerating}>
              {t("generateDescription.retry")}
            </Button>
            <Button variant="outline" onClick={handleNext}>
              {t("generateDescription.skip")}
            </Button>
          </div>
        </div>
      )}

      {pageState === "saving" && (
        <div className="flex flex-1 flex-col items-center justify-center gap-4">
          <Spinner className="size-8" />
          <p className="text-muted-foreground">{t("generateDescription.saving")}</p>
        </div>
      )}

      {showHistory && history.length > 0 && (
        <Dialog open={showHistory} onOpenChange={setShowHistory}>
          <DialogContent className="max-h-[80vh] max-w-2xl overflow-y-auto">
            <DialogHeader>
              <DialogTitle>{t("generateDescription.historyTitle")}</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              {history.map((v, i) => (
                <div key={i} className="rounded-lg border p-4">
                  <p className="text-muted-foreground mb-2 text-xs">
                    {t("generateDescription.version", {
                      date: new Date(v.created_at).toLocaleString(),
                    })}
                    {v.model && <span> &middot; {v.model}</span>}
                  </p>
                  {v.description_en && <p className="mb-1 text-sm">{v.description_en}</p>}
                  {v.description_ar && (
                    <p className="text-sm" dir="rtl">
                      {v.description_ar}
                    </p>
                  )}
                  <Button
                    variant="outline"
                    size="sm"
                    className="mt-2"
                    onClick={() => {
                      setEnText(v.description_en ?? "");
                      setArText(v.description_ar ?? "");
                      setShowHistory(false);
                    }}
                  >
                    {t("generateDescription.restore")}
                  </Button>
                </div>
              ))}
            </div>
          </DialogContent>
        </Dialog>
      )}
    </PageLayout>
  );
}
