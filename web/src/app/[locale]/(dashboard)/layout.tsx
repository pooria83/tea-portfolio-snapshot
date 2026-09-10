"use client";

import { useSyncExternalStore, useEffect } from "react";
import type { ReactNode } from "react";
import { useRouter, usePathname } from "@/i18n/routing";
import { useAppSelector } from "@/store/hooks";
import { SidebarProvider, SidebarInset } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/dashboard/AppSidebar";
import { DashboardHeader } from "@/components/dashboard/DashboardHeader";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorBoundary } from "@/components/providers/ErrorBoundary";

function getHydrationSnapshot() {
  return typeof document !== "undefined";
}

function subscribe(_callback: () => void): () => void {
  return () => {};
}

type Props = {
  children: ReactNode;
};

export default function DashboardLayout({ children }: Props) {
  const hydrated = useSyncExternalStore(subscribe, getHydrationSnapshot, () => false);
  const router = useRouter();
  const pathname = usePathname();
  const step = useAppSelector((s) => s.auth.step);
  const loading = useAppSelector((s) => s.auth.loading);
  const user = useAppSelector((s) => s.auth.user);

  useEffect(() => {
    if (hydrated && !loading && step !== "authenticated") {
      router.replace("/login");
      return;
    }
    if (hydrated && !loading && step === "authenticated" && user) {
      const wantsAdmin = pathname.startsWith("/admin");
      if (wantsAdmin && user.role !== "admin") {
        router.replace("/seller");
      }
    }
  }, [hydrated, loading, step, router, pathname, user]);

  if (!hydrated) {
    return null;
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center p-8">
        <div className="w-full max-w-md space-y-4">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
        </div>
      </div>
    );
  }

  if (step !== "authenticated") {
    return null;
  }

  if (pathname.startsWith("/admin") && user?.role !== "admin") {
    return null;
  }

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <DashboardHeader />
        <div className="flex-1 overflow-auto p-6">
          <ErrorBoundary>{children}</ErrorBoundary>
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}
