"use client";

import { useTranslations } from "next-intl";
import { useParams } from "next/navigation";
import { PageLayout } from "@/components/layout/PageLayout";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { StoreForm } from "@/components/store/StoreForm";
import { StoreMembersSection } from "@/components/store/StoreMembersSection";
import { useGetStoreQuery } from "@/store/api/storeApi";

export default function EditStorePage() {
  const s = useTranslations("store");
  const params = useParams();
  const storeId = params.id as string;
  const { data: store, isLoading, error } = useGetStoreQuery(storeId);

  if (isLoading) {
    return (
      <PageLayout variant="narrow">
        <Skeleton className="h-8 w-48" />
        <div className="space-y-4">
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-9 w-full" />
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      </PageLayout>
    );
  }

  if (error || !store) {
    return (
      <PageLayout variant="narrow">
        <p className="text-destructive">{s("loadOptionsFailed")}</p>
      </PageLayout>
    );
  }

  return (
    <PageLayout variant="narrow">
      <StoreForm initialData={store} />
      <Separator className="my-8" />
      <StoreMembersSection storeId={store.id} myRole={store.my_role} />
    </PageLayout>
  );
}
