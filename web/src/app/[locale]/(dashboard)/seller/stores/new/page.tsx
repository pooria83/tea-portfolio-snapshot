"use client";

import { useTranslations } from "next-intl";
import { PageLayout } from "@/components/layout/PageLayout";
import { StoreForm } from "@/components/store/StoreForm";

export default function CreateStorePage() {
  const s = useTranslations("store");

  return (
    <PageLayout variant="narrow">
      <h1 className="text-2xl font-bold">{s("createTitle")}</h1>
      <StoreForm />
    </PageLayout>
  );
}
