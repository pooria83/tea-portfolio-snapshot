"use client";

import { useParams } from "next/navigation";
import { PageLayout } from "@/components/layout/PageLayout";
import { ProductForm } from "@/components/product/ProductForm";

export default function NewProductPage() {
  const params = useParams();
  const storeId = params.id as string;

  return (
    <PageLayout variant="narrow" className="flex h-full flex-col gap-6 space-y-0">
      <ProductForm storeId={storeId} />
    </PageLayout>
  );
}
