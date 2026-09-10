"use client";

import { useCallback, useState } from "react";
import { useTranslations } from "next-intl";
import { MenuIcon, HomeIcon, InfoIcon, LogInIcon } from "lucide-react";
import { Link, usePathname } from "@/i18n/routing";
import { LanguageSwitcher } from "@/components/shared/LanguageSwitcher";
import { useCloseOnBack } from "@/hooks/useCloseOnBack";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";

const NAV_LINKS = [
  { href: "/", key: "home", icon: HomeIcon },
  { href: "/about", key: "about", icon: InfoIcon },
] as const;

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const t = useTranslations("website");
  const pathname = usePathname();

  return (
    <>
      {NAV_LINKS.map((link) => {
        const active = pathname === link.href;
        const Icon = link.icon;
        return (
          <Link
            key={link.href}
            href={link.href}
            onClick={onNavigate}
            className={cn(
              "text-foreground/80 hover:text-foreground flex items-center gap-1.5 transition-colors",
              active && "text-foreground font-semibold",
            )}
          >
            <Icon className="size-4" />
            {t(link.key)}
          </Link>
        );
      })}
    </>
  );
}

export function WebsiteNavbar() {
  const t = useTranslations("website");
  const appT = useTranslations("app");
  const [menuOpen, setMenuOpen] = useState(false);

  const closeMenu = useCallback(() => setMenuOpen(false), []);

  useCloseOnBack(menuOpen, closeMenu, "navbar-menu");

  return (
    <header className="bg-background/80 sticky top-0 z-40 border-b backdrop-blur">
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between gap-4 px-4">
        <div className="flex items-center gap-6">
          <Link href="/" className="text-foreground text-lg font-semibold">
            {appT("name")}
          </Link>
          <div className="hidden items-center gap-6 md:flex">
            <NavLinks />
          </div>
        </div>

        <div className="hidden items-center gap-3 md:flex">
          <Button render={<Link href="/login" />} size="sm">
            <LogInIcon className="mr-1.5 size-4" />
            {t("login")}
          </Button>
          <LanguageSwitcher />
        </div>

        <div className="flex items-center gap-2 md:hidden">
          <LanguageSwitcher />
          <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
            <SheetTrigger
              render={<Button variant="outline" size="icon" aria-label={t("openMenu")} />}
            >
              <MenuIcon className="size-5" />
            </SheetTrigger>
            <SheetContent side="right" showCloseButton={false}>
              <SheetTitle className="sr-only">{appT("name")}</SheetTitle>
              <nav className="flex flex-col gap-4 p-4">
                <NavLinks onNavigate={() => setMenuOpen(false)} />
              </nav>
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </header>
  );
}
