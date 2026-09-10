"use client";

import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import { PageLayout } from "@/components/layout/PageLayout";
import { Skeleton } from "@/components/ui/skeleton";
import { ProductForm } from "@/components/product/ProductForm";
import { useGetStoreProductQuery } from "@/store/api/productApi";

export default function EditProductPage() {
  const t = useTranslations("product");
  const params = useParams();
  const storeId = params.id as string;
  const productId = params.productId as string;
  const {
    data: product,
    isLoading,
    error,
  } = useGetStoreProductQuery({
    store_id: storeId,
    product_id: productId,
  });

  if (isLoading) {
    return (
      <PageLayout variant="narrow">
        <div className="space-y-4">
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      </PageLayout>
    );
  }

  if (error || !product) {
    return (
      <PageLayout variant="narrow">
        <p className="text-destructive">{t("error")}</p>
      </PageLayout>
    );
  }

  return (
    <PageLayout variant="narrow" className="flex h-full flex-col gap-6 space-y-0">
      <ProductForm storeId={storeId} initialData={product} />
    </PageLayout>
  );
}
