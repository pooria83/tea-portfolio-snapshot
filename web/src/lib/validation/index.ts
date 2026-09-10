import { z } from "zod";

export function withValidation<T>(schema: z.ZodType<T>) {
  return (res: unknown): T => {
    const data = (res as { data: unknown }).data;
    const result = schema.safeParse(data);
    if (!result.success) {
      console.error("[Validation] API response mismatch:", result.error.issues);
    }
    return data as T;
  };
}

export const CategoryOptionSchema = z.object({
  id: z.string(),
  name: z.string(),
});

export const StoreListItemSchema = z.object({
  id: z.string(),
  name: z.string(),
  category_name_ar: z.string(),
  category_name_en: z.string(),
  category_name_fa: z.string(),
  store_type_name_ar: z.string(),
  store_type_name_en: z.string(),
  store_type_name_fa: z.string(),
  logo_url: z.string().nullable(),
  is_active: z.boolean(),
  created_at: z.string(),
});

export const StoreResponseSchema = z.object({
  id: z.string(),
  owner_id: z.string(),
  name: z.string(),
  category_id: z.string(),
  category_name_ar: z.string(),
  category_name_en: z.string(),
  category_name_fa: z.string(),
  store_type_id: z.string(),
  store_type_name_ar: z.string(),
  store_type_name_en: z.string(),
  store_type_name_fa: z.string(),
  description: z.string().nullable(),
  phone: z.string(),
  logo_url: z.string().nullable(),
  address: z.string(),
  location_lat: z.number(),
  location_lng: z.number(),
  website: z.string().nullable(),
  instagram: z.string().nullable(),
  is_active: z.boolean(),
  country_code: z.string(),
  price_unit_code: z.string(),
  country_name_ar: z.string(),
  country_name_en: z.string(),
  country_name_fa: z.string(),
  currency_name_ar: z.string(),
  currency_name_en: z.string(),
  currency_name_fa: z.string(),
  currency_symbol: z.string(),
  active_products_count: z.number(),
  working_hours: z.array(
    z.object({
      day_of_week: z.number(),
      open_time: z.string().nullable(),
      close_time: z.string().nullable(),
      is_closed: z.boolean(),
    }),
  ),
  members: z.array(
    z.object({
      id: z.string(),
      user_id: z.string(),
      role: z.enum(["owner", "manager"]),
      full_name: z.string().nullable(),
      phone: z.string().nullable(),
      email: z.string().nullable(),
    }),
  ),
  my_role: z.enum(["owner", "manager"]).nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const AuthResponseSchema = z.object({
  success: z.boolean(),
  data: z.object({
    access_token: z.string(),
    refresh_token: z.string(),
    token_type: z.string(),
  }),
});

export const PaginationMetaSchema = z.object({
  skip: z.number(),
  limit: z.number(),
  total: z.number(),
  has_next: z.boolean(),
  has_previous: z.boolean(),
});

export const PaginatedItemsSchema = <T extends z.ZodTypeAny>(itemSchema: T) =>
  z.object({
    items: z.array(itemSchema),
    meta: PaginationMetaSchema,
  });
