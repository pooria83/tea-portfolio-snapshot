"use client";

import { useTranslations } from "next-intl";
import { HiOutlineShoppingBag, HiOutlineCube, HiOutlineUser } from "react-icons/hi";
import { PageLayout } from "@/components/layout/PageLayout";
import { Skeleton } from "@/components/ui/skeleton";
import { useGetMyProductsStatsQuery } from "@/store/api/productApi";
import { useGetMyStoresQuery } from "@/store/api/storeApi";
import { useGetProfileQuery } from "@/store/api/profileApi";
import { DashboardTile } from "@/components/shared/DashboardTile";

export default function SellerDashboardPage() {
  const t = useTranslations("dashboard");
  const { data: productStats, isLoading: productsLoading } = useGetMyProductsStatsQuery();
  const { data: stores = [], isLoading: storesLoading } = useGetMyStoresQuery();
  const { data: profile, isLoading: profileLoading } = useGetProfileQuery();

  const totalProducts = productStats?.total ?? 0;
  const activeCount = productStats?.active ?? 0;

  const isLoading = productsLoading || storesLoading || profileLoading;

  const iconSize = "size-6";

  return (
    <PageLayout variant="wide">
      <h1 className="text-2xl font-bold">{t("title")}</h1>

      {isLoading ? (
        <div className="mt-6 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="space-y-3 rounded-2xl p-6">
              <Skeleton className="size-10 rounded-xl" />
              <Skeleton className="h-10 w-20" />
              <Skeleton className="h-4 w-32" />
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-6 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
          <DashboardTile
            href="/seller/products"
            icon={<HiOutlineCube className={iconSize} />}
            label={t("totalProducts")}
            value={totalProducts}
            subtext={`${t("activeProducts")}: ${activeCount}`}
            className="bg-gradient-to-br from-blue-600 to-indigo-700"
          />

          <DashboardTile
            href="/seller/stores"
            icon={<HiOutlineShoppingBag className={iconSize} />}
            label={t("totalStores")}
            value={stores.length}
            className="bg-gradient-to-br from-emerald-500 to-teal-700"
          />

          <DashboardTile
            href="/seller/profile"
            icon={<HiOutlineUser className={iconSize} />}
            label={t("myProfile")}
            subtext={profile?.email ?? ""}
            className="bg-gradient-to-br from-violet-600 to-purple-800"
          />
        </div>
      )}
    </PageLayout>
  );
}
