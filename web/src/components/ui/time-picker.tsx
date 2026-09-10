"use client";

import { useState } from "react";
import { FiClock } from "react-icons/fi";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

const HOURS = Array.from({ length: 24 }, (_, i) => i.toString().padStart(2, "0"));
const MINUTES = ["00", "15", "30", "45"];

interface TimePickerProps {
  value: string | null;
  onChange: (value: string | null) => void;
  disabled?: boolean;
}

export function TimePicker({ value, onChange, disabled }: TimePickerProps) {
  const [open, setOpen] = useState(false);

  const [selHour, selMin] = (value || "00:00").split(":") as [string, string];

  const handleSelect = (hour: string, minute: string) => {
    onChange(`${hour}:${minute}`);
    setOpen(false);
  };

  return (
    <Popover open={open && !disabled} onOpenChange={setOpen}>
      <PopoverTrigger
        render={
          <Button
            type="button"
            variant="outline"
            className={cn(
              "h-8 w-28 justify-start gap-1.5 px-2.5 text-xs font-normal",
              !value && "text-muted-foreground",
            )}
            disabled={disabled}
          />
        }
      >
        <FiClock className="size-3.5 shrink-0" />
        {value || "HH:MM"}
      </PopoverTrigger>
      <PopoverContent className="w-auto p-2" align="start">
        <div className="flex gap-2">
          <div className="flex max-h-48 flex-col gap-0.5 overflow-y-auto">
            {HOURS.map((h) => (
              <button
                key={h}
                type="button"
                onClick={() => handleSelect(h, selMin)}
                className={cn(
                  "hover:bg-accent rounded px-3 py-1 text-xs tabular-nums transition-colors",
                  h === selHour && "bg-accent font-medium",
                )}
              >
                {h}
              </button>
            ))}
          </div>
          <div className="flex max-h-48 flex-col gap-0.5 overflow-y-auto">
            {MINUTES.map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => handleSelect(selHour, m)}
                className={cn(
                  "hover:bg-accent rounded px-3 py-1 text-xs tabular-nums transition-colors",
                  m === selMin && "bg-accent font-medium",
                )}
              >
                {m}
              </button>
            ))}
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
