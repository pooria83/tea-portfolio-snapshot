import { z } from "zod";
import { isSafeHref } from "@/lib/url";

const optionalSafeUrl = z.string().refine((value) => !value || isSafeHref(value), "invalidUrl");

export const storeSchema = z.object({
  name: z.string().min(1, "required"),
  category_id: z.string().min(1, "required"),
  store_type_id: z.string().min(1, "required"),
  country_code: z.string().min(1, "required"),
  price_unit_code: z.string().min(1, "required"),
  description: z.string().optional(),
  phone: z.string().min(1, "required"),
  address: z.string().min(1, "required"),
  location: z.object({ lat: z.number(), lng: z.number() }),
  logo_url: z.string().optional(),
  website: optionalSafeUrl.optional(),
  instagram: optionalSafeUrl.optional(),
  working_hours: z
    .array(
      z.object({
        day_of_week: z.number(),
        is_closed: z.boolean(),
        open_time: z.string().nullable(),
        close_time: z.string().nullable(),
      }),
    )
    .refine((hours) => hours.some((h) => !h.is_closed), "atLeastOneOpen"),
});

export type StoreFormValues = z.infer<typeof storeSchema>;
