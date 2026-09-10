"use client";

import { useCallback, useState, type FormEvent } from "react";
import { useTranslations, useLocale } from "next-intl";
import { useRouter } from "@/i18n/routing";
import { HiOutlineCube, HiOutlineFilter, HiOutlineSearch, HiOutlinePlus } from "react-icons/hi";
import { toast } from "sonner";
import { PageLayout } from "@/components/layout/PageLayout";
import type { PageResult } from "@/hooks/useInfiniteProducts";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useLazyGetMyProductsPageQuery } from "@/store/api/productApi";
import { useGetMyStoresQuery } from "@/store/api/storeApi";
import { useInfiniteProducts } from "@/hooks/useInfiniteProducts";
import { ProductCard } from "@/components/product/ProductCard";
import { ProductViewDialog } from "@/components/product/ProductViewDialog";
import type { ProductListItem, StoreListItem } from "@/types/api";

function ProductsSearchForm({
  searchQuery,
  onSearch,
}: {
  searchQuery: string;
  onSearch: (query: string) => void;
}) {
  const t = useTranslations("product");
  const ct = useTranslations("common");
  const [inputQuery, setInputQuery] = useState("");

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    onSearch(inputQuery.trim());
  };

  const handleClear = () => {
    setInputQuery("");
    onSearch("");
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-wrap items-center gap-2">
      <Input
        placeholder={t("searchPlaceholder")}
        value={inputQuery}
        onChange={(event) => setInputQuery(event.target.value)}
        className="h-9 w-48"
      />
      <Button type="submit" variant="default" size="sm" className="h-9 gap-1">
        <HiOutlineSearch className="size-4" />
        {t("searchProducts")}
      </Button>
      {searchQuery && (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={handleClear}
          className="h-9 text-xs"
        >
          {ct("clear")}
        </Button>
      )}
    </form>
  );
}

export default function MyProductsPage() {
  const t = useTranslations("product");
  const st = useTranslations("store");
  const locale = useLocale();
  const router = useRouter();
  const [selectedProductId, setSelectedProductId] = useState<string | null>(null);
  const [selectedStoreId, setSelectedStoreId] = useState<string | null>(null);
  const [storeFilter, setStoreFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [storeDialogOpen, setStoreDialogOpen] = useState(false);
  const [fetchPage] = useLazyGetMyProductsPageQuery();
  const { items, isLoading, isLoadingMore, sentinelRef } = useInfiniteProducts<ProductListItem>(
    (p): Promise<{ data?: PageResult<ProductListItem> }> =>
      fetchPage({
        ...p,
        ...(searchQuery ? { q: searchQuery } : {}),
        ...(storeFilter === "all" ? {} : { store_id: storeFilter }),
      }).then((r) => {
        const result: { data?: PageResult<ProductListItem> } = {};
        if (r.data) result.data = r.data;
        return result;
      }),
    [searchQuery, storeFilter],
  );
  const { data: stores = [] } = useGetMyStoresQuery();

  const handleSearch = useCallback((query: string) => {
    setSearchQuery(query);
  }, []);

  function handleCreateProduct() {
    if (stores.length === 0) {
      toast.warning(st("noStores"));
      router.push("/seller/stores");
      return;
    }
    if (stores.length === 1) {
      const firstStore = stores[0];
      if (firstStore) {
        router.push(`/seller/stores/${firstStore.id}/products/new`);
      }
      return;
    }
    setStoreDialogOpen(true);
  }

  function handleSelectStore(store: StoreListItem) {
    setStoreDialogOpen(false);
    router.push(`/seller/stores/${store.id}/products/new`);
  }

  const handleView = useCallback((product: ProductListItem) => {
    setSelectedProductId(product.id);
    setSelectedStoreId(product.store_id);
  }, []);

  const selectedStoreName =
    storeFilter === "all"
      ? t("allStores")
      : stores.find((s) => s.id === storeFilter)?.name || storeFilter;

  return (
    <PageLayout variant="wide">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">{t("title")}</h1>
        <Button variant="default" size="sm" className="h-9 gap-1" onClick={handleCreateProduct}>
          <HiOutlinePlus className="size-4" />
          {t("createTitle")}
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <ProductsSearchForm searchQuery={searchQuery} onSearch={handleSearch} />
        <HiOutlineFilter className="text-muted-foreground size-4 shrink-0" />
        <Select
          value={storeFilter}
          onValueChange={(value) => {
            if (value) setStoreFilter(value);
          }}
        >
          <SelectTrigger className="h-9 w-44">
            <SelectValue>{selectedStoreName}</SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("allStores")}</SelectItem>
            {stores.map((s) => (
              <SelectItem key={s.id} value={s.id}>
                {s.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {(() => {
        if (isLoading) {
          return (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="space-y-3">
                  <Skeleton className="aspect-[4/3] w-full rounded-xl" />
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-3 w-1/2" />
                </div>
              ))}
            </div>
          );
        }

        if (items.length === 0) {
          return (
            <div className="flex flex-col items-center gap-4 rounded-lg border border-dashed p-12 text-center">
              <HiOutlineCube className="text-muted-foreground size-12" />
              <p className="text-muted-foreground">{t("noProducts")}</p>
              <Button variant="default" onClick={handleCreateProduct}>
                {t("createFirst")}
              </Button>
            </div>
          );
        }

        return (
          <>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {items.map((product) => (
                <ProductCard
                  key={product.id}
                  product={product}
                  storeId={product.store_id}
                  storeName={product.store_name}
                  locale={locale}
                  onView={() => handleView(product)}
                />
              ))}
            </div>
            {isLoadingMore && (
              <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={`skeleton-${i}`} className="space-y-3">
                    <Skeleton className="aspect-[4/3] w-full rounded-xl" />
                    <Skeleton className="h-4 w-3/4" />
                    <Skeleton className="h-3 w-1/2" />
                  </div>
                ))}
              </div>
            )}
            <div ref={sentinelRef} className="h-4" />
          </>
        );
      })()}

      <ProductViewDialog
        open={selectedProductId != null}
        storeId={selectedStoreId ?? ""}
        productId={selectedProductId ?? ""}
        onOpenChange={(open) => {
          if (!open) setSelectedProductId(null);
        }}
      />

      <Dialog open={storeDialogOpen} onOpenChange={setStoreDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{st("chooseStore")}</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-2">
            {stores.map((store) => (
              <Button
                key={store.id}
                variant="outline"
                className="h-auto justify-start px-4 py-3"
                onClick={() => handleSelectStore(store)}
              >
                <div className="flex flex-col items-start gap-0.5">
                  <span className="text-sm font-medium">{store.name}</span>
                  {store.category_name_en && (
                    <span className="text-muted-foreground text-xs">{store.category_name_en}</span>
                  )}
                </div>
              </Button>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </PageLayout>
  );
}
