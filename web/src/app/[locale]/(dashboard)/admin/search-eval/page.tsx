"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import {
  useEvalGenerateQueriesMutation,
  useEvalImportQueriesMutation,
  useEvalSearchMutation,
  useGetEvalMetricsQuery,
  useGetEvalQueriesQuery,
  useSaveEvalJudgmentsMutation,
  useUpdateEvalQueryMutation,
} from "@/store/api/adminApi";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { DataTable, type DataTableColumn } from "@/components/ui/data-table";
import { PaginationBar } from "@/components/ui/pagination-bar";
import { usePaginationTable } from "@/hooks/usePaginationTable";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { RetryingThumbnail } from "@/components/chat/RetryingThumbnail";
import { toast } from "sonner";
import { extractApiError } from "@/lib/api";
import type { EvalQueryItem, EvalSearchResultItem } from "@/types/api";

const PAGE_SIZE = 20;

type StatusVariant = "default" | "secondary" | "destructive" | "outline";

function statusVariant(status: string): StatusVariant {
  switch (status) {
    case "evaluated": {
      return "default";
    }
    case "pending": {
      return "secondary";
    }
    case "skipped": {
      return "outline";
    }
    default: {
      return "outline";
    }
  }
}

function sourceVariant(source: string): StatusVariant {
  switch (source) {
    case "llm": {
      return "default";
    }
    case "seed": {
      return "secondary";
    }
    default: {
      return "outline";
    }
  }
}

function MetricCard({
  title,
  queryCount,
  mrr,
  recall,
}: {
  title: string;
  queryCount: number;
  mrr: number;
  recall: number;
}) {
  const t = useTranslations("admin.searchEval");
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">{title}</CardTitle>
        <CardDescription>
          {t("evaluatedQueries")}: {queryCount}
        </CardDescription>
      </CardHeader>
      <CardContent className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-muted-foreground text-sm">{t("mrr")}</p>
          <p className="text-2xl font-bold">{mrr.toFixed(4)}</p>
        </div>
        <div>
          <p className="text-muted-foreground text-sm">{t("recall")}</p>
          <p className="text-2xl font-bold">{recall.toFixed(4)}</p>
        </div>
      </CardContent>
    </Card>
  );
}

function JudgeDialog({
  query,
  open,
  onOpenChange,
}: {
  query: EvalQueryItem | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const t = useTranslations("admin.searchEval");
  const commonT = useTranslations("common");
  const [runSearch, { isLoading: searching }] = useEvalSearchMutation();
  const [saveJudgments, { isLoading: saving }] = useSaveEvalJudgmentsMutation();
  const [updateQuery] = useUpdateEvalQueryMutation();
  const [results, setResults] = useState<EvalSearchResultItem[]>([]);
  const [relevantIds, setRelevantIds] = useState<Set<string>>(new Set());
  const [searched, setSearched] = useState(false);
  const ranRef = useRef(false);

  useEffect(() => {
    if (!open || !query || ranRef.current) {
      return;
    }
    ranRef.current = true;
    setResults([]);
    setRelevantIds(new Set());
    setSearched(false);
    void (async () => {
      try {
        const res = await runSearch({
          query: query.text,
          locale: query.locale,
          limit: 20,
        }).unwrap();
        setResults(res.results);
        setRelevantIds(new Set());
        setSearched(true);
      } catch (error) {
        toast.error(extractApiError(error, commonT("error")));
        setSearched(true);
      }
    })();
  }, [open, query, runSearch, commonT]);

  useEffect(() => {
    if (!open) {
      ranRef.current = false;
    }
  }, [open]);

  const toggleRelevant = useCallback((id: string) => {
    setRelevantIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const handleSave = useCallback(async () => {
    if (!query) {
      return;
    }
    try {
      const byId = new Map(results.filter((r) => r.id).map((r) => [r.id, r]));
      const judgments = Array.from(relevantIds).map((id) => ({
        product_id: id,
        relevant: true,
        rank: byId.get(id)?.rank ?? null,
      }));
      await saveJudgments({ queryId: query.id, body: { judgments } }).unwrap();
      toast.success(t("saved", { count: judgments.length }));
      onOpenChange(false);
    } catch (error) {
      toast.error(extractApiError(error, commonT("error")));
    }
  }, [query, results, relevantIds, saveJudgments, t, commonT, onOpenChange]);

  const handleSkip = useCallback(async () => {
    if (!query) {
      return;
    }
    try {
      await updateQuery({ queryId: query.id, body: { status: "skipped" } }).unwrap();
      toast.success(t("markedSkipped"));
      onOpenChange(false);
    } catch (error) {
      toast.error(extractApiError(error, commonT("error")));
    }
  }, [query, updateQuery, t, commonT, onOpenChange]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{t("judgeTitle")}</DialogTitle>
          <DialogDescription>
            {query ? (
              <>
                {t("judgeDescription")}
                <span className="mt-2 block rounded-md border p-2 font-medium" dir="auto">
                  {query.text}
                </span>
              </>
            ) : (
              t("judgeDescription")
            )}
          </DialogDescription>
        </DialogHeader>

        {searching && <p className="text-muted-foreground text-sm">{commonT("loading")}</p>}

        {!searching && searched && results.length === 0 && (
          <p className="text-muted-foreground text-sm">{t("noResults")}</p>
        )}

        {!searching && results.length > 0 && (
          <div className="space-y-2">
            {results.map((result) => (
              <div key={result.id} className="flex items-center gap-3 rounded-md border p-2">
                <Checkbox
                  checked={relevantIds.has(result.id)}
                  onCheckedChange={() => toggleRelevant(result.id)}
                  aria-label={t("relevant")}
                />
                <div className="bg-muted flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded">
                  {result.image_url ? (
                    <RetryingThumbnail src={result.image_url} alt={result.name ?? result.id} />
                  ) : (
                    <span className="text-muted-foreground text-xs">—</span>
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium" dir="auto">
                    {result.name ?? result.id}
                  </p>
                  <p className="text-muted-foreground text-sm">
                    {t("rank")}: {result.rank} · {t("score")}: {result.score.toFixed(4)}
                    {result.brand ? ` · ${result.brand}` : ""}
                  </p>
                </div>
                <div className="shrink-0 text-sm font-medium">
                  {result.price == null
                    ? "—"
                    : `${result.price.toLocaleString()} ${result.currency}`}
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="outline" disabled={saving} onClick={() => void handleSkip()}>
            {t("markSkipped")}
          </Button>
          <Button disabled={saving || relevantIds.size === 0} onClick={() => void handleSave()}>
            {t("saveJudgments")}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function FilterTextInput({ onSearch }: { onSearch: (value: string) => void }) {
  const t = useTranslations("admin.searchEval");
  const commonT = useTranslations("common");
  const [value, setValue] = useState("");

  const submit = () => onSearch(value.trim());

  return (
    <div className="flex gap-2">
      <Input
        id="eval-text-filter"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            submit();
          }
        }}
        placeholder={t("searchPlaceholder")}
      />
      <Button variant="outline" onClick={submit}>
        {commonT("search")}
      </Button>
    </div>
  );
}

export default function SearchEvalPage() {
  const t = useTranslations("admin.searchEval");
  const commonT = useTranslations("common");
  const [localeFilter, setLocaleFilter] = useState<string | undefined>();
  const [sourceFilter, setSourceFilter] = useState<string | undefined>();
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [appliedText, setAppliedText] = useState("");
  const [count, setCount] = useState(10);
  const [generateLocales, setGenerateLocales] = useState<string[]>(["en", "ar"]);
  const [importJson, setImportJson] = useState("");
  const [judgeQuery, setJudgeQuery] = useState<EvalQueryItem | null>(null);
  const [judgeOpen, setJudgeOpen] = useState(false);
  const { skip, page, pageSize, next, previous, reset } = usePaginationTable(PAGE_SIZE);

  const { data: metrics } = useGetEvalMetricsQuery();
  const [generateQueries, { isLoading: generating }] = useEvalGenerateQueriesMutation();
  const [importQueries, { isLoading: importing }] = useEvalImportQueriesMutation();

  const { data, isLoading, isFetching, isError } = useGetEvalQueriesQuery({
    skip,
    limit: PAGE_SIZE,
    ...(localeFilter === undefined ? {} : { locale: localeFilter }),
    ...(sourceFilter === undefined ? {} : { source: sourceFilter }),
    ...(statusFilter === undefined ? {} : { status: statusFilter }),
    ...(appliedText === "" ? {} : { q: appliedText }),
  });

  const handleLocaleFilter = useCallback(
    (value: string | null) => {
      setLocaleFilter(value === "all" ? undefined : (value ?? undefined));
      reset();
    },
    [reset],
  );

  const handleSourceFilter = useCallback(
    (value: string | null) => {
      setSourceFilter(value === "all" ? undefined : (value ?? undefined));
      reset();
    },
    [reset],
  );

  const handleStatusFilter = useCallback(
    (value: string | null) => {
      setStatusFilter(value === "all" ? undefined : (value ?? undefined));
      reset();
    },
    [reset],
  );

  const handleTextSearch = useCallback(
    (value: string) => {
      setAppliedText(value);
      reset();
    },
    [reset],
  );

  const toggleGenerateLocale = useCallback((locale: string) => {
    setGenerateLocales((prev) =>
      prev.includes(locale) ? prev.filter((l) => l !== locale) : [...prev, locale],
    );
  }, []);

  const handleGenerate = useCallback(async () => {
    try {
      const result = await generateQueries({
        count,
        locales: generateLocales,
      }).unwrap();
      toast.success(t("generated", { count: result.length }));
    } catch (error) {
      toast.error(extractApiError(error, commonT("error")));
    }
  }, [generateQueries, count, generateLocales, t, commonT]);

  const handleImport = useCallback(async () => {
    let parsed: unknown;
    try {
      parsed = JSON.parse(importJson);
    } catch {
      toast.error(t("invalidJson"));
      return;
    }
    if (!Array.isArray(parsed)) {
      toast.error(t("invalidJson"));
      return;
    }
    try {
      const result = await importQueries({
        queries: parsed as { text: string; locale: string; relevant_ids: string[] }[],
      }).unwrap();
      toast.success(
        t("imported", {
          created: result.created,
          judgments: result.judgments_created,
          skipped: result.skipped,
        }),
      );
      setImportJson("");
    } catch (error) {
      toast.error(extractApiError(error, commonT("error")));
    }
  }, [importJson, importQueries, t, commonT]);

  const openJudge = useCallback((item: EvalQueryItem) => {
    setJudgeQuery(item);
    setJudgeOpen(true);
  }, []);

  const totalPages = data ? Math.ceil(data.total / pageSize) : 1;

  const columns = useMemo<DataTableColumn<EvalQueryItem>[]>(
    () => [
      {
        header: t("queryText"),
        cell: (item) => (
          <div className="min-w-0">
            <p className="truncate font-medium" dir="auto">
              {item.text}
            </p>
            {item.rewritten_query && (
              <p className="text-muted-foreground truncate text-xs" dir="auto">
                → {item.rewritten_query}
              </p>
            )}
          </div>
        ),
        className: "font-medium",
      },
      {
        header: t("locale"),
        cell: (item) => <Badge variant="outline">{item.locale}</Badge>,
      },
      {
        header: t("source"),
        cell: (item) => <Badge variant={sourceVariant(item.source)}>{t(item.source)}</Badge>,
      },
      {
        header: t("status"),
        cell: (item) => <Badge variant={statusVariant(item.status)}>{t(item.status)}</Badge>,
      },
      {
        header: t("createdAt"),
        cell: (item) => (
          <span className="text-muted-foreground text-sm">
            {new Date(item.created_at).toLocaleDateString()}
          </span>
        ),
      },
      {
        header: t("actions"),
        align: "right",
        cell: (item) => (
          <Button variant="outline" size="sm" onClick={() => openJudge(item)}>
            {t("judge")}
          </Button>
        ),
      },
    ],
    [t, openJudge],
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

      <div>
        <h2 className="mb-2 text-lg font-semibold">{t("metricsTitle")}</h2>
        <p className="text-muted-foreground mb-4 text-sm">{t("metricsDescription")}</p>
        {metrics ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <MetricCard
              title={t("overall")}
              queryCount={metrics.overall?.query_count ?? 0}
              mrr={metrics.overall?.mrr_10 ?? 0}
              recall={metrics.overall?.recall_10 ?? 0}
            />
            <MetricCard
              title={t("localeEn")}
              queryCount={metrics.per_locale[0]?.query_count ?? 0}
              mrr={metrics.per_locale[0]?.mrr_10 ?? 0}
              recall={metrics.per_locale[0]?.recall_10 ?? 0}
            />
            <MetricCard
              title={t("localeAr")}
              queryCount={metrics.per_locale[1]?.query_count ?? 0}
              mrr={metrics.per_locale[1]?.mrr_10 ?? 0}
              recall={metrics.per_locale[1]?.recall_10 ?? 0}
            />
          </div>
        ) : (
          <p className="text-muted-foreground text-sm">{t("noMetrics")}</p>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("generateTitle")}</CardTitle>
            <CardDescription>{t("generateDescription")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="generate-count">{t("count")}</Label>
                <Input
                  id="generate-count"
                  type="number"
                  min={1}
                  max={50}
                  value={count}
                  onChange={(event) => setCount(Math.max(1, Number(event.target.value) || 1))}
                />
              </div>
              <div className="space-y-1.5">
                <Label>{t("locales")}</Label>
                <div className="flex gap-6 pt-1">
                  <label className="flex items-center gap-2 text-sm">
                    <Checkbox
                      checked={generateLocales.includes("en")}
                      onCheckedChange={() => toggleGenerateLocale("en")}
                    />
                    EN
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <Checkbox
                      checked={generateLocales.includes("ar")}
                      onCheckedChange={() => toggleGenerateLocale("ar")}
                    />
                    AR
                  </label>
                </div>
              </div>
            </div>
            <Button
              disabled={generating || generateLocales.length === 0}
              onClick={() => void handleGenerate()}
            >
              {generating ? t("generating") : t("generate")}
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("importTitle")}</CardTitle>
            <CardDescription>{t("importDescription")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Textarea
              value={importJson}
              onChange={(event) => setImportJson(event.target.value)}
              placeholder={t("importPlaceholder")}
              className="min-h-[120px] font-mono text-xs"
            />
            <Button
              disabled={importing || importJson.trim() === ""}
              onClick={() => void handleImport()}
            >
              {importing ? t("importing") : t("import")}
            </Button>
          </CardContent>
        </Card>
      </div>

      <div>
        <h2 className="mb-4 text-lg font-semibold">{t("tableTitle")}</h2>
        <div className="mb-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="space-y-1.5">
            <Label htmlFor="eval-locale-filter">{t("filterLocale")}</Label>
            <Select value={localeFilter ?? "all"} onValueChange={handleLocaleFilter}>
              <SelectTrigger id="eval-locale-filter" className="w-full">
                <SelectValue placeholder={t("all")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t("all")}</SelectItem>
                <SelectItem value="en">EN</SelectItem>
                <SelectItem value="ar">AR</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="eval-source-filter">{t("filterSource")}</Label>
            <Select value={sourceFilter ?? "all"} onValueChange={handleSourceFilter}>
              <SelectTrigger id="eval-source-filter" className="w-full">
                <SelectValue placeholder={t("all")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t("all")}</SelectItem>
                <SelectItem value="manual">{t("manual")}</SelectItem>
                <SelectItem value="llm">{t("llm")}</SelectItem>
                <SelectItem value="seed">{t("seed")}</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="eval-status-filter">{t("filterStatus")}</Label>
            <Select value={statusFilter ?? "all"} onValueChange={handleStatusFilter}>
              <SelectTrigger id="eval-status-filter" className="w-full">
                <SelectValue placeholder={t("all")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t("all")}</SelectItem>
                <SelectItem value="pending">{t("pending")}</SelectItem>
                <SelectItem value="evaluated">{t("evaluated")}</SelectItem>
                <SelectItem value="skipped">{t("skipped")}</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="eval-text-filter">{t("queryText")}</Label>
            <FilterTextInput onSearch={handleTextSearch} />
          </div>
        </div>

        <DataTable
          columns={columns}
          rows={data?.items}
          rowKey={(item) => item.id}
          emptyText={t("noQueries")}
        />

        {data && data.total > PAGE_SIZE && (
          <PaginationBar
            page={page}
            totalPages={totalPages}
            canPrevious={page > 1}
            canNext={skip + PAGE_SIZE < data.total}
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
      </div>

      {judgeOpen && <JudgeDialog query={judgeQuery} open onOpenChange={setJudgeOpen} />}
    </div>
  );
}
