export interface CategoryOption {
  id: string;
  name: string;
}

export interface StoreTypeOption {
  id: string;
  name: string;
}

export interface WorkingHourInput {
  day_of_week: number;
  open_time: string | null;
  close_time: string | null;
  is_closed: boolean;
}

export interface StoreWorkingHour {
  id: string;
  day_of_week: number;
  open_time: string | null;
  close_time: string | null;
  is_closed: boolean;
}

export interface CountryOption {
  code: string;
  name: string;
}

export interface CurrencyOption {
  code: string;
  name: string;
  symbol: string;
}

export interface StoreCreate {
  name: string;
  category_id: string;
  store_type_id: string;
  description?: string;
  phone: string;
  address: string;
  location_lat: number;
  location_lng: number;
  logo_url?: string;
  website?: string;
  instagram?: string;
  country_code: string;
  price_unit_code: string;
  working_hours: WorkingHourInput[];
}

export interface StoreUpdate {
  name?: string;
  category_id?: string;
  store_type_id?: string;
  description?: string;
  phone?: string;
  address?: string;
  location_lat?: number;
  location_lng?: number;
  logo_url?: string;
  website?: string;
  instagram?: string;
  country_code?: string;
  price_unit_code?: string;
  working_hours?: WorkingHourInput[];
}

export interface StoreMember {
  id: string;
  user_id: string;
  role: "owner" | "manager";
  full_name: string | null;
  phone: string | null;
  email: string | null;
}

export interface StoreMemberAddRequest {
  phone?: string;
  email?: string;
  role: "owner" | "manager";
}

export interface StoreResponse {
  id: string;
  owner_id: string;
  name: string;
  category_id: string;
  category_name_ar: string;
  category_name_en: string;
  category_name_fa: string;
  store_type_id: string;
  store_type_name_ar: string;
  store_type_name_en: string;
  store_type_name_fa: string;
  description: string | null;
  phone: string;
  logo_url: string | null;
  address: string;
  location_lat: number;
  location_lng: number;
  website: string | null;
  instagram: string | null;
  is_active: boolean;
  country_code: string;
  price_unit_code: string;
  country_name_ar: string;
  country_name_en: string;
  country_name_fa: string;
  currency_name_ar: string;
  currency_name_en: string;
  currency_name_fa: string;
  currency_symbol: string;
  active_products_count: number;
  working_hours: WorkingHourInput[];
  members: StoreMember[];
  my_role: "owner" | "manager" | null;
  created_at: string;
  updated_at: string;
}

export interface StoreListItem {
  id: string;
  name: string;
  category_name_ar: string;
  category_name_en: string;
  category_name_fa: string;
  store_type_name_ar: string;
  store_type_name_en: string;
  store_type_name_fa: string;
  logo_url: string | null;
  is_active: boolean;
  created_at: string;
}
