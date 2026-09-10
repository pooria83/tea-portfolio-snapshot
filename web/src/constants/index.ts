export const APP_NAME = "AskTea.ai";
export const APP_VERSION = "0.1.0";

export const ROLES = {
  ADMIN: "admin" as const,
  SELLER: "seller" as const,
} as const;

export const ROUTES = {
  LOGIN: "/login",
  ADMIN_DASHBOARD: "/admin",
  SELLER_DASHBOARD: "/seller",
} as const;

export const API_PREFIX = "/api/v1";
