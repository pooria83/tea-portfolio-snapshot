"use client";

import { useState, useCallback, useEffect, useMemo, useRef } from "react";
import { useTranslations } from "next-intl";
import {
  useGetEmbeddingCronProductsQuery,
  useGetEmbeddingCronProductDetailQuery,
  useGetEmbedModelsQuery,
  useGetActiveEmbeddingModelQuery,
  useReindexEmbeddingsMutation,
} from "@/store/api/adminApi";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { DataTable, type DataTableColumn } from "@/components/ui/data-table";
import { PaginationBar } from "@/components/ui/pagination-bar";
import { usePaginationTable } from "@/hooks/usePaginationTable";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { extractApiError } from "@/lib/api";
import type { EmbeddingCronProductItem } from "@/types/api";

const PAGE_SIZE = 20;

function statusVariant(status: string | null): "default" | "secondary" | "destructive" | "outline" {
  switch (status) {
    case "done": {
      return "default";
    }
    case "pending":
    case "generating": {
      return "secondary";
    }
    case "error": {
      return "destructive";
    }
    default: {
      return "outline";
    }
  }
}

function DetailModal({
  productId,
  open,
  onOpenChange,
}: {
  productId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const t = useTranslations("settings.embeddingCron");
  const commonT = useTranslations("common");
  const { data: detail, isFetching } = useGetEmbeddingCronProductDetailQuery(productId ?? "", {
    skip: !productId,
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[80vh] max-w-5xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{detail?.name_en ?? detail?.name_ar ?? t("viewDetailTitle")}</DialogTitle>
        </DialogHeader>
        {isFetching && <p className="text-muted-foreground text-sm">{commonT("loading")}</p>}
        {detail && (
          <div className="space-y-4">
            <div>
              <Label>{t("sku")}</Label>
              <Input value={detail.sku ?? ""} readOnly />
            </div>
            <div>
              <Label>{t("modelRows")}</Label>
              <div className="space-y-2">
                {detail.embeddings.length === 0 ? (
                  <p className="text-muted-foreground text-sm">{t("noEmbeddings")}</p>
                ) : (
                  detail.embeddings.map((embedding) => (
                    <div
                      key={embedding.model_name}
                      className="flex flex-wrap items-center gap-3 rounded-md border p-3 text-sm"
                    >
                      <span className="font-medium">{embedding.model_name}</span>
                      <Badge variant={statusVariant(embedding.embedding_status)}>
                        {t(embedding.embedding_status)}
                      </Badge>
                      {embedding.updated_at && (
                        <span className="text-muted-foreground">
                          {new Date(embedding.updated_at).toLocaleString()}
                        </span>
                      )}
                      {embedding.embedding_error && (
                        <span className="text-destructive w-full text-xs">
                          {embedding.embedding_error}
                        </span>
                      )}
                    </div>
                  ))
                )}
              </div>
            </div>
            <div>
              <Label>{t("embeddingText")}</Label>
              <Textarea
                value={detail.embedding_text ?? ""}
                readOnly
                className="min-h-[200px] font-mono text-xs"
              />
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default function EmbeddingCronProductsPage() {
  const t = useTranslations("settings.embeddingCron");
  const commonT = useTranslations("common");
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [modelFilter, setModelFilter] = useState<string | undefined>();
  const modelInitRef = useRef(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [reindexOpen, setReindexOpen] = useState(false);
  const { skip, page, pageSize, next, previous, reset } = usePaginationTable(PAGE_SIZE);

  const { data: embedModels } = useGetEmbedModelsQuery();
  const { data: activeModelData } = useGetActiveEmbeddingModelQuery();
  const [reindexEmbeddings, { isLoading: reindexing }] = useReindexEmbeddingsMutation();

  const activeModel = activeModelData?.active_model;

  useEffect(() => {
    if (!modelInitRef.current && activeModel) {
      modelInitRef.current = true;
      setModelFilter(activeModel);
      reset();
    }
  }, [activeModel, reset]);

  const { data, isLoading, isFetching, isError } = useGetEmbeddingCronProductsQuery({
    skip,
    limit: PAGE_SIZE,
    ...(statusFilter === undefined ? {} : { embedding_status: statusFilter }),
    ...(modelFilter === undefined ? {} : { model: modelFilter }),
  });

  const handleStatusFilter = useCallback(
    (status: string | null) => {
      setStatusFilter(status === "all" ? undefined : (status ?? undefined));
      reset();
    },
    [reset],
  );

  const handleModelFilter = useCallback(
    (model: string | null) => {
      modelInitRef.current = true;
      setModelFilter(model === "all" ? undefined : (model ?? undefined));
      reset();
    },
    [reset],
  );

  const openDetail = useCallback((item: EmbeddingCronProductItem) => {
    setSelectedId(item.id);
    setDetailOpen(true);
  }, []);

  const handleReindex = useCallback(async () => {
    try {
      const result = await reindexEmbeddings().unwrap();
      toast.success(t("reindexed", { count: result.affected, model: result.active_model }));
      setReindexOpen(false);
    } catch (error) {
      toast.error(extractApiError(error, commonT("error")));
    }
  }, [reindexEmbeddings, t, commonT]);

  const meta = data?.meta;
  const activeModels = embedModels?.filter((m) => m.is_active).map((m) => m.model_name) ?? [];
  const totalPages = meta ? Math.ceil(meta.total / pageSize) : 1;

  const columns = useMemo<DataTableColumn<EmbeddingCronProductItem>[]>(
    () => [
      {
        header: t("productName"),
        cell: (item) => item.name_en ?? item.name_ar ?? item.name_fa ?? "—",
        className: "font-medium",
      },
      { header: t("sku"), cell: (item) => item.sku ?? "—" },
      {
        header: t("model"),
        cell: (item) => <span className="text-sm">{item.embedding_model ?? "—"}</span>,
      },
      {
        header: t("status"),
        cell: (item) => (
          <Badge variant={statusVariant(item.embedding_status)}>
            {item.embedding_status ? t(item.embedding_status) : "—"}
          </Badge>
        ),
      },
      {
        header: t("errorMessage"),
        cell: (item) => (
          <span className="text-muted-foreground max-w-[200px] truncate text-sm">
            {item.embedding_error ?? "—"}
          </span>
        ),
      },
      {
        header: t("updatedAt"),
        cell: (item) => (
          <span className="text-muted-foreground text-sm">
            {item.updated_at ? new Date(item.updated_at).toLocaleString() : "—"}
          </span>
        ),
      },
      {
        header: t("actions"),
        align: "right",
        cell: (item) => (
          <Button variant="outline" size="sm" onClick={() => openDetail(item)}>
            {t("viewDetail")}
          </Button>
        ),
      },
    ],
    [t, openDetail],
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-12">
        <p className="text-muted-foreground">{commonT("loading")}</p>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 p-12">
        <p className="text-destructive">{commonT("error")}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{t("title")}</h1>
          <p className="text-muted-foreground text-sm">{t("description")}</p>
        </div>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-stretch">
        {activeModel && (
          <div className="bg-muted flex flex-1 items-center rounded-md border px-4 py-2 text-sm">
            <span className="text-muted-foreground">{t("activeModel")}: </span>
            <span className="font-medium">{activeModel}</span>
          </div>
        )}
        <AlertDialog open={reindexOpen} onOpenChange={setReindexOpen}>
          <Button
            variant="destructive"
            className="w-full sm:w-auto"
            disabled={reindexing}
            onClick={() => setReindexOpen(true)}
          >
            {t("reindex")}
          </Button>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{t("reindexConfirmTitle")}</AlertDialogTitle>
              <AlertDialogDescription>{t("reindexConfirmWarning")}</AlertDialogDescription>
              <AlertDialogDescription>
                {t("reindexConfirmDesc", { model: activeModel ?? "" })}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>{commonT("cancel")}</AlertDialogCancel>
              <AlertDialogAction
                variant="destructive"
                disabled={reindexing}
                onClick={() => void handleReindex()}
              >
                {t("reindex")}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:max-w-3xl">
        <div className="space-y-1.5">
          <Label htmlFor="status-filter">{t("status")}</Label>
          <Select value={statusFilter ?? "all"} onValueChange={handleStatusFilter}>
            <SelectTrigger id="status-filter" className="w-full">
              <SelectValue placeholder={t("all")} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t("all")}</SelectItem>
              <SelectItem value="pending">{t("pending")}</SelectItem>
              <SelectItem value="generating">{t("generating")}</SelectItem>
              <SelectItem value="done">{t("done")}</SelectItem>
              <SelectItem value="error">{t("error")}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="model-filter">{t("model")}</Label>
          <Select value={modelFilter ?? "all"} onValueChange={handleModelFilter}>
            <SelectTrigger id="model-filter" className="w-full">
              <SelectValue placeholder={t("allModels")} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t("allModels")}</SelectItem>
              {activeModels.map((model) => (
                <SelectItem key={model} value={model}>
                  {model}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <DataTable
        columns={columns}
        rows={data?.items}
        rowKey={(item) => `${item.id}-${item.embedding_model}`}
        emptyText={t("noProducts")}
      />

      {meta && meta.total > PAGE_SIZE && (
        <PaginationBar
          page={page}
          totalPages={totalPages}
          canPrevious={page > 1}
          canNext={Boolean(meta.has_next)}
          onPrevious={previous}
          onNext={next}
          previousLabel={t("previous")}
          nextLabel={t("next")}
          pageInfo={t("pageInfo", { current: page, total: totalPages })}
        />
      )}

      {isFetching && (
        <p className="text-muted-foreground text-center text-sm">{commonT("loading")}</p>
      )}

      {detailOpen && <DetailModal productId={selectedId} open onOpenChange={setDetailOpen} />}
    </div>
  );
}
