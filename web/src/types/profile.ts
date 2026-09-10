export interface UserProfile {
  id: string;
  full_name: string | null;
  email: string | null;
  phone: string;
  role: string;
  avatar_url: string | null;
  address: string | null;
  location_lat: number | null;
  location_lng: number | null;
  preferred_language: string;
  is_active: boolean;
  has_google: boolean;
  created_at: string;
}

export interface UserProfileUpdate {
  full_name?: string;
  avatar_url?: string;
  address?: string;
  location_lat?: number;
  location_lng?: number;
  preferred_language?: string;
}
