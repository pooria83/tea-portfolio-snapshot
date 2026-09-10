"use client";

import { useTranslations } from "next-intl";
import { useFieldArray, useWatch, Controller, type Control } from "react-hook-form";
import { Switch } from "@/components/ui/switch";
import { TimePicker } from "@/components/ui/time-picker";
import { getWeekdayNames } from "@/lib/weekdays";
import { FiClock } from "react-icons/fi";
import type { StoreFormValues } from "@/lib/store-schema";

interface WorkingHoursEditorProps {
  control: Control<StoreFormValues>;
  locale: string;
}

export function WorkingHoursEditor({ control, locale }: WorkingHoursEditorProps) {
  const s = useTranslations("store");
  const weekdays = getWeekdayNames(locale);
  const whValues = useWatch({ control, name: "working_hours" }) || [];
  const { fields } = useFieldArray({
    control,
    name: "working_hours",
  });

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FiClock className="size-4" />
          <span className="text-sm font-medium">{s("workingHours")}</span>
        </div>
      </div>
      <div className="space-y-2">
        {weekdays.map((day, index) => {
          const field = fields[index];
          if (!field) return null;
          return (
            <div key={field.id} className="flex items-center gap-2">
              <span className="w-20 text-sm">{day.name}</span>
              <Controller
                name={`working_hours.${index}.is_closed` as const}
                control={control}
                render={({ field: closedField }) => (
                  <label className="flex items-center gap-1.5 text-xs">
                    <Switch
                      checked={closedField.value}
                      onCheckedChange={closedField.onChange}
                      size="sm"
                    />
                    {s("closed")}
                  </label>
                )}
              />
              <Controller
                name={`working_hours.${index}.open_time` as const}
                control={control}
                render={({ field: openField }) => (
                  <TimePicker
                    value={openField.value}
                    onChange={openField.onChange}
                    disabled={whValues[index]?.is_closed ?? false}
                  />
                )}
              />
              <span className="text-muted-foreground text-xs">{s("to")}</span>
              <Controller
                name={`working_hours.${index}.close_time` as const}
                control={control}
                render={({ field: closeField }) => (
                  <TimePicker
                    value={closeField.value}
                    onChange={closeField.onChange}
                    disabled={whValues[index]?.is_closed ?? false}
                  />
                )}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}
