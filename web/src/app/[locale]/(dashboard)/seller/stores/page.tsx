"use client";

import { useTranslations, useLocale } from "next-intl";
import { Link } from "@/i18n/routing";
import { HiOutlineShoppingBag, HiOutlinePlus, HiOutlineCog } from "react-icons/hi";
import { PageLayout } from "@/components/layout/PageLayout";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";
import { useGetMyStoresQuery } from "@/store/api/storeApi";

export default function StoresPage() {
  const navT = useTranslations("nav");
  const s = useTranslations("store");
  const locale = useLocale();
  const { data: stores = [], isLoading } = useGetMyStoresQuery();

  const categoryName = (store: {
    category_name_ar: string;
    category_name_en: string;
    category_name_fa: string;
  }) => {
    const key = `category_name_${locale}` as keyof typeof store;
    return store[key] || store.category_name_en;
  };

  const storeTypeName = (store: {
    store_type_name_ar: string;
    store_type_name_en: string;
    store_type_name_fa: string;
  }) => {
    const key = `store_type_name_${locale}` as keyof typeof store;
    return store[key] || store.store_type_name_en;
  };

  return (
    <PageLayout variant="wide">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{navT("stores")}</h1>
        <Link href="/seller/stores/new" className={cn(buttonVariants({ variant: "default" }))}>
          <HiOutlinePlus className="size-4" />
          {s("createStore")}
        </Link>
      </div>

      {(() => {
        if (isLoading) {
          return (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <Card key={i}>
                  <CardHeader>
                    <Skeleton className="h-5 w-32" />
                  </CardHeader>
                  <CardContent>
                    <Skeleton className="h-4 w-24" />
                    <Skeleton className="mt-2 h-4 w-20" />
                  </CardContent>
                </Card>
              ))}
            </div>
          );
        }

        if (stores.length === 0) {
          return (
            <div className="flex flex-col items-center gap-4 rounded-lg border border-dashed p-12 text-center">
              <HiOutlineShoppingBag className="text-muted-foreground size-12" />
              <p className="text-muted-foreground">{s("noStores")}</p>
              <Link
                href="/seller/stores/new"
                className={cn(buttonVariants({ variant: "default" }))}
              >
                {s("createFirstStore")}
              </Link>
            </div>
          );
        }

        return (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {stores.map((store) => (
              <Card key={store.id} className="hover:bg-muted/50 transition-colors">
                <Link href={`/seller/stores/${store.id}/edit`}>
                  <CardHeader>
                    <div className="flex items-center gap-3">
                      <Avatar>
                        {store.logo_url ? (
                          <AvatarImage src={store.logo_url} alt={store.name} />
                        ) : (
                          <AvatarFallback>
                            <HiOutlineShoppingBag className="size-4" />
                          </AvatarFallback>
                        )}
                      </Avatar>
                      <div className="min-w-0 flex-1">
                        <CardTitle className="truncate">{store.name}</CardTitle>
                        <p className="text-muted-foreground text-xs">
                          {categoryName(store)} &middot; {storeTypeName(store)}
                        </p>
                      </div>
                      <HiOutlineCog className="text-muted-foreground size-4 shrink-0" />
                    </div>
                  </CardHeader>
                </Link>
                <CardContent>
                  <Badge variant={store.is_active ? "default" : "secondary"}>
                    {store.is_active ? s("active") : s("inactive")}
                  </Badge>
                </CardContent>
              </Card>
            ))}
          </div>
        );
      })()}
    </PageLayout>
  );
}
