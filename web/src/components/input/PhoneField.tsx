"use client";

import { useState, useMemo } from "react";
import { useLocale } from "next-intl";
import { FiChevronDown } from "react-icons/fi";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Command,
  CommandInput,
  CommandList,
  CommandItem,
  CommandEmpty,
  CommandGroup,
} from "@/components/ui/command";
import { InputGroup, InputGroupAddon, InputGroupInput } from "@/components/ui/input-group";
import { countries, defaultCountry, getCountryName, type Country } from "@/constants/countries";

interface PhoneFieldProps {
  value?: string;
  onChange: (value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  error?: string;
}

export function PhoneField({ value = "", onChange, placeholder, disabled }: PhoneFieldProps) {
  const locale = useLocale();
  const [open, setOpen] = useState(false);

  const { selectedCountry, localNumber } = useMemo(() => {
    const trimmed = value.trim();
    let country = defaultCountry;
    let local = trimmed;
    for (const c of countries) {
      if (trimmed.startsWith(c.dialCode)) {
        country = c;
        local = trimmed.slice(c.dialCode.length);
        break;
      }
    }
    return { selectedCountry: country, localNumber: local };
  }, [value]);

  const handleCountrySelect = (country: Country) => {
    setOpen(false);
    onChange(`${country.dialCode}${localNumber}`);
  };

  const handleLocalChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange(`${selectedCountry.dialCode}${e.target.value}`);
  };

  return (
    <InputGroup>
      <InputGroupAddon className="p-0" align="inline-start">
        <Popover open={open} onOpenChange={setOpen}>
          <PopoverTrigger
            render={
              <Button
                type="button"
                variant="ghost"
                className="h-8 rounded-md px-2 text-sm font-normal"
                disabled={disabled}
              />
            }
          >
            <span className="text-base leading-none">{selectedCountry.flag}</span>
            <span className="text-xs font-medium" dir="ltr">
              {selectedCountry.dialCode}
            </span>
            <FiChevronDown className="text-muted-foreground size-3 shrink-0 opacity-60" />
          </PopoverTrigger>
          <PopoverContent className="w-72 p-0" align="start">
            <Command>
              <CommandInput placeholder="Search country..." className="h-9" />
              <CommandList>
                <CommandEmpty>No country found</CommandEmpty>
                <CommandGroup>
                  {countries.map((country) => (
                    <CommandItem
                      key={country.code}
                      value={`${country.name} ${country.nameAr} ${country.nameFa} ${country.dialCode} ${country.code}`}
                      onSelect={() => handleCountrySelect(country)}
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
      </InputGroupAddon>
      <InputGroupInput
        type="tel"
        dir="ltr"
        placeholder={placeholder}
        value={localNumber}
        onChange={handleLocalChange}
        className="text-left"
        disabled={disabled}
      />
    </InputGroup>
  );
}
