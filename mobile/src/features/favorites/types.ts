/**
 * A saved product as returned by GET /users/me/favorites. Mirrors the
 * ChatProduct shape used by product cards.
 */
export interface FavoriteProduct {
  id: string;
  store_id: string;
  store_name: string | null;
  name_ar: string | null;
  name_en: string | null;
  name_fa: string | null;
  brand: string | null;
  price: number | null;
  original_price: number | null;
  sale_price: number | null;
  currency: string | null;
  image_url: string | null;
  created_at: string;
}
