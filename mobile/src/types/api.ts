export interface SendOtpRequest {
  phone: string;
}

export interface VerifyOtpRequest {
  phone: string;
  code: string;
}

export interface GoogleAuthRequest {
  id_token: string;
  client_type: 'web' | 'android' | 'ios';
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface User {
  id: string;
  email: string | null;
  phone: string | null;
  username: string | null;
  full_name: string | null;
  role: string;
  is_active: boolean;
  avatar_url: string | null;
  address: string | null;
  location_lat: number | null;
  location_lng: number | null;
  preferred_language: string;
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

export interface UploadFileResponse {
  file_name: string;
  original_name: string;
  content_type: string;
  size: number;
  url: string;
}

export interface LinkGoogleMobileRequest {
  id_token: string;
}

export interface ApiResponse<T> {
  success: boolean;
  data: T;
}

export interface ApiErrorBody {
  success: false;
  error?: {
    code?: string;
    message?: string;
    translation_key?: string | null;
    request_id?: string;
  };
  detail?: string | string[];
}

export interface ApiError {
  detail: string;
}
