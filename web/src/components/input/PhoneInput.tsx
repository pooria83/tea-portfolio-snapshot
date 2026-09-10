"use client";

import { useState } from "react";
import { useTranslations, useLocale } from "next-intl";
import { FiPhone, FiChevronDown } from "react-icons/fi";
import { FcGoogle } from "react-icons/fc";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Command,
  CommandInput,
  CommandList,
  CommandItem,
  CommandEmpty,
  CommandGroup,
} from "@/components/ui/command";
import { countries, defaultCountry, getCountryName, type Country } from "@/constants/countries";

interface CountryPhoneInputProps {
  onSubmit: (phone: string) => void;
  onGoogleLogin: () => void;
  loading: boolean;
  error: string | null;
  onClearError: () => void;
}

export function PhoneInputSection({
  onSubmit,
  onGoogleLogin,
  loading,
  error,
  onClearError,
}: CountryPhoneInputProps) {
  const t = useTranslations("auth");
  const locale = useLocale();
  const [selectedCountry, setSelectedCountry] = useState<Country>(defaultCountry);
  const [localNumber, setLocalNumber] = useState("");
  const [open, setOpen] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const fullPhone = `${selectedCountry.dialCode}${localNumber}`;
    onSubmit(fullPhone);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="phone">{t("phone")}</Label>
        <div className="flex items-center gap-0" dir="ltr">
          <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger
              render={
                <Button
                  type="button"
                  variant="outline"
                  className="h-9 min-w-[6.5rem] shrink-0 rounded-l-lg rounded-r-none border-r-0 px-2.5"
                />
              }
            >
              <span className="text-base leading-none">{selectedCountry.flag}</span>
              <span className="text-sm font-medium" dir="ltr">
                {selectedCountry.dialCode}
              </span>
              <FiChevronDown className="text-muted-foreground size-3.5 shrink-0 opacity-60" />
            </PopoverTrigger>
            <PopoverContent className="w-80 p-0" align="start">
              <Command>
                <CommandInput placeholder={t("searchCountry")} className="h-9" />
                <CommandList>
                  <CommandEmpty>{t("noCountryFound")}</CommandEmpty>
                  <CommandGroup>
                    {countries.map((country) => (
                      <CommandItem
                        key={country.code}
                        value={`${country.name} ${country.nameAr} ${country.nameFa} ${country.dialCode} ${country.code}`}
                        onSelect={() => {
                          setSelectedCountry(country);
                          setOpen(false);
                          if (error) onClearError();
                        }}
                        className="gap-2"
                      >
                        <span className="text-base leading-none">{country.flag}</span>
                        <span className="flex-1 text-sm">{getCountryName(locale, country)}</span>
                        <span className="text-muted-foreground text-xs" dir="ltr">
                          {country.dialCode}
                        </span>
                      </CommandItem>
                    ))}
                  </CommandGroup>
                </CommandList>
              </Command>
            </PopoverContent>
          </Popover>
          <div className="relative flex-1">
            <FiPhone className="text-muted-foreground absolute top-1/2 left-3 -translate-y-1/2" />
            <Input
              id="phone"
              type="tel"
              dir="ltr"
              placeholder={t("phonePlaceholder")}
              value={localNumber}
              onChange={(e) => {
                setLocalNumber(e.target.value);
                if (error) onClearError();
              }}
              className="rounded-l-none pl-10 text-left"
              required
              aria-invalid={!!error}
              aria-describedby={error ? "phone-error" : undefined}
            />
          </div>
        </div>
        {error && (
          <p id="phone-error" className="text-destructive text-sm" role="alert">
            {error}
          </p>
        )}
      </div>
      <Button type="submit" className="w-full" disabled={loading}>
        {loading ? t("sendOtp") + "..." : t("sendOtp")}
      </Button>
      <div className="relative flex items-center gap-3">
        <Separator className="flex-1" />
        <span className="text-muted-foreground text-xs">{t("or")}</span>
        <Separator className="flex-1" />
      </div>
      <Button type="button" variant="outline" className="w-full gap-2" onClick={onGoogleLogin}>
        <FcGoogle className="size-5" />
        {t("googleLogin")}
      </Button>
    </form>
  );
}
