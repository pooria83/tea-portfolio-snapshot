"use client";

import { memo } from "react";
import { useTranslations, useLocale } from "next-intl";
import { Link, useRouter } from "@/i18n/routing";
import {
  HiOutlineViewGrid,
  HiOutlineShoppingBag,
  HiOutlineClipboardList,
  HiOutlineChip,
  HiOutlineCog,
  HiOutlineUser,
  HiOutlineCollection,
  HiOutlineClock,
  HiOutlineSearch,
  HiOutlineServer,
  HiOutlineChatAlt2,
  HiOutlineClipboardCheck,
} from "react-icons/hi";
import { FiSun, FiMoon, FiLogOut, FiShuffle } from "react-icons/fi";
import { useTheme } from "@/components/providers/ThemeProvider";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarHeader,
} from "@/components/ui/sidebar";
import { useAppSelector, useAppDispatch } from "@/store/hooks";
import { logout, setPreferredView } from "@/store/slices/auth";
import { Button } from "@/components/ui/button";
import { LanguageSwitcher } from "@/components/shared/LanguageSwitcher";

const adminNavItems = [
  { href: "/admin", label: "dashboard", icon: HiOutlineViewGrid },
  { href: "/admin/data", label: "catalogData", icon: HiOutlineCollection },
  { href: "/admin/product-search", label: "productSearch", icon: HiOutlineSearch },
  { href: "/admin/cron", label: "cronJobs", icon: HiOutlineClock },
  { href: "/admin/chats", label: "conversations", icon: HiOutlineChatAlt2 },
  { href: "/admin/search-eval", label: "searchEval", icon: HiOutlineClipboardCheck },
  { href: "/admin/settings/llm", label: "llmSettings", icon: HiOutlineCog },
  { href: "/admin/settings/prompts", label: "prompts", icon: HiOutlineClipboardList },
  { href: "/admin/settings/ai-engine", label: "aiEngineSettings", icon: HiOutlineServer },
  { href: "/admin/settings/system", label: "systemSettings", icon: HiOutlineCog },
  { href: "/admin/settings/scrapers", label: "scraperHeaders", icon: HiOutlineChip },
];

const sellerNavItems = [
  { href: "/seller", label: "dashboard", icon: HiOutlineViewGrid },
  { href: "/seller/stores", label: "stores", icon: HiOutlineShoppingBag },
  { href: "/seller/products", label: "products", icon: HiOutlineShoppingBag },
  { href: "/seller/profile", label: "profile", icon: HiOutlineUser },
];

export const AppSidebar = memo(function AppSidebar() {
  const t = useTranslations("nav");
  const commonT = useTranslations("common");
  const user = useAppSelector((s) => s.auth.user);
  const preferredView = useAppSelector((s) => s.auth.preferredView);
  const isAdmin = user?.role === "admin";
  const effectiveRole = isAdmin ? preferredView : user?.role;
  const navItems = effectiveRole === "seller" ? sellerNavItems : adminNavItems;
  const brandLink = effectiveRole === "seller" ? "/seller" : "/admin";
  const locale = useLocale();
  const router = useRouter();
  const { theme, setTheme } = useTheme();

  const dispatch = useAppDispatch();
  const sidebarSide = locale === "en" ? "left" : "right";

  return (
    <Sidebar side={sidebarSide} aria-label="Main navigation">
      <SidebarHeader className="px-4 py-3">
        <Link href={brandLink} className="text-lg font-bold">
          AskTea.ai
        </Link>
      </SidebarHeader>
      <SidebarContent>
        {isAdmin && (
          <SidebarGroup>
            <SidebarGroupContent>
              <SidebarMenu>
                <SidebarMenuItem>
                  <SidebarMenuButton
                    onClick={() => {
                      const next = preferredView === "seller" ? "admin" : "seller";
                      dispatch(setPreferredView(next));
                      router.push(next === "admin" ? "/admin" : "/seller");
                    }}
                  >
                    <FiShuffle className="size-4" />
                    <span>
                      {preferredView === "seller" ? t("switchToAdmin") : t("switchToSeller")}
                    </span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        )}
        <SidebarGroup>
          <SidebarGroupLabel>{t("dashboard")}</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => {
                const Icon = item.icon;
                return (
                  <SidebarMenuItem key={item.href}>
                    <SidebarMenuButton render={<Link href={item.href} />}>
                      <Icon className="size-4" />
                      <span>{t(item.label)}</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter>
        <div className="flex items-center gap-1 px-2">
          <LanguageSwitcher />
          <Button
            variant="ghost"
            size="icon"
            className="size-8"
            aria-label={theme === "dark" ? commonT("themeLight") : commonT("themeDark")}
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          >
            {theme === "dark" ? <FiSun className="size-4" /> : <FiMoon className="size-4" />}
          </Button>
        </div>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              onClick={() => {
                dispatch(logout());
                router.replace("/login");
              }}
            >
              <FiLogOut className="size-4" />
              <span>{t("logout")}</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
});
