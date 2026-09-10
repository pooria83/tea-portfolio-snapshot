"use client";

import { useState } from "react";
import { useLocale } from "next-intl";
import { useRouter, usePathname } from "@/i18n/routing";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandList, CommandItem, CommandGroup } from "@/components/ui/command";
import { FiGlobe, FiCheck } from "react-icons/fi";
import { routing } from "@/i18n/routing";

const localeNames: Record<string, string> = {
  ar: "العربية",
  en: "English",
  fa: "فارسی",
};

const localeFlags: Record<string, string> = {
  ar: "🇸🇦",
  en: "🇬🇧",
  fa: "🇮🇷",
};

interface LanguageSwitcherProps {
  align?: "start" | "end";
  "aria-label"?: string;
}

export function LanguageSwitcher({
  align = "start",
  "aria-label": ariaLabel = "Switch language",
}: LanguageSwitcherProps) {
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();
  const [langOpen, setLangOpen] = useState(false);

  return (
    <Popover open={langOpen} onOpenChange={setLangOpen}>
      <PopoverTrigger
        render={<Button variant="ghost" size="icon" className="size-8" aria-label={ariaLabel} />}
      >
        <FiGlobe className="size-4" />
      </PopoverTrigger>
      <PopoverContent className="w-40 min-w-0 p-0" align={align}>
        <Command>
          <CommandList>
            <CommandGroup>
              {routing.locales.map((loc) => (
                <CommandItem
                  key={loc}
                  value={loc}
                  onSelect={() => {
                    setLangOpen(false);
                    router.replace(pathname, { locale: loc });
                  }}
                  className="gap-2"
                >
                  <span>{localeFlags[loc]}</span>
                  <span className="flex-1">{localeNames[loc]}</span>
                  {loc === locale && <FiCheck className="size-3.5" />}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
