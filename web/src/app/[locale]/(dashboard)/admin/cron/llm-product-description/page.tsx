"use client";

import { useCallback, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { useGetCronProductsQuery, useGetCronProductDetailQuery } from "@/store/api/adminApi";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { DataTable, type DataTableColumn } from "@/components/ui/data-table";
import { PaginationBar } from "@/components/ui/pagination-bar";
import { usePaginationTable } from "@/hooks/usePaginationTable";
import type { CronProductItem } from "@/types/api";

const PAGE_SIZE = 20;

function DetailModal({
  productId,
  open,
  onOpenChange,
}: {
  productId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const t = useTranslations("settings.cron");
  const commonT = useTranslations("common");
  const { data: detail, isFetching } = useGetCronProductDetailQuery(productId ?? "", {
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
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>{t("sku")}</Label>
                <Input value={detail.sku ?? ""} readOnly />
              </div>
              <div>
                <Label>{t("model")}</Label>
                <Input value={detail.model ?? ""} readOnly />
              </div>
            </div>
            <div>
              <Label>{t("prompt")}</Label>
              <Textarea
                value={detail.prompt ?? ""}
                readOnly
                className="min-h-[200px] font-mono text-xs"
              />
            </div>
            <div>
              <Label>{t("descriptionEn")}</Label>
              <Textarea value={detail.description_en ?? ""} readOnly className="min-h-[120px]" />
            </div>
            <div>
              <Label>{t("descriptionAr")}</Label>
              <Textarea value={detail.description_ar ?? ""} readOnly className="min-h-[120px]" />
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default function CronProductsPage() {
  const t = useTranslations("settings.cron");
  const commonT = useTranslations("common");
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const { skip, page, pageSize, next, previous, reset } = usePaginationTable(PAGE_SIZE);

  const { data, isLoading, isFetching, isError } = useGetCronProductsQuery({
    skip,
    limit: PAGE_SIZE,
    ...(statusFilter === undefined ? {} : { status: statusFilter }),
  });

  const handleFilter = useCallback(
    (status?: string) => {
      setStatusFilter(status);
      reset();
    },
    [reset],
  );

  const openDetail = useCallback((item: CronProductItem) => {
    setSelectedId(item.id);
    setDetailOpen(true);
  }, []);

  const meta = data?.meta;
  const totalPages = meta ? Math.ceil(meta.total / pageSize) : 1;

  const columns = useMemo<DataTableColumn<CronProductItem>[]>(
    () => [
      {
        header: t("productName"),
        cell: (item) => item.name_en ?? item.name_ar ?? item.name_fa ?? "—",
        className: "font-medium",
      },
      { header: t("sku"), cell: (item) => item.sku ?? "—" },
      {
        header: t("status"),
        cell: (item) => (
          <Badge variant={item.status === "generated" ? "default" : "secondary"}>
            {item.status === "generated" ? t("generated") : t("pending")}
          </Badge>
        ),
      },
      {
        header: t("model"),
        cell: (item) => <span className="text-muted-foreground text-sm">{item.model ?? "—"}</span>,
      },
      {
        header: t("lastGenerated"),
        cell: (item) => (
          <span className="text-muted-foreground text-sm">
            {item.last_generated_at ? new Date(item.last_generated_at).toLocaleString() : "—"}
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
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{t("title")}</h1>
        <p className="text-muted-foreground text-sm">{t("description")}</p>
      </div>

      <div className="flex items-center gap-2">
        <Button
          variant={statusFilter === undefined ? "default" : "outline"}
          size="sm"
          onClick={() => handleFilter()}
        >
          {t("all")}
        </Button>
        <Button
          variant={statusFilter === "pending" ? "default" : "outline"}
          size="sm"
          onClick={() => handleFilter("pending")}
        >
          {t("pending")}
        </Button>
        <Button
          variant={statusFilter === "generated" ? "default" : "outline"}
          size="sm"
          onClick={() => handleFilter("generated")}
        >
          {t("generated")}
        </Button>
      </div>

      <DataTable
        columns={columns}
        rows={data?.items}
        rowKey={(item) => item.id}
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
