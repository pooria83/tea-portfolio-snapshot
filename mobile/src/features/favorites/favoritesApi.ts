import client from '../../services/api/client';
import {unwrapEnvelope} from '../../services/api/envelope';
import type {FavoriteProduct} from './types';

const FAVORITES_BASE = '/users/me/favorites';

export const fetchFavorites = async (): Promise<FavoriteProduct[]> => {
  const response = await client.get(`${FAVORITES_BASE}?skip=0&limit=100`);
  return unwrapEnvelope<FavoriteProduct[]>(response);
};

export const addFavorite = async (
  storeId: string,
  productId: string,
): Promise<void> => {
  await client.put(`${FAVORITES_BASE}/${storeId}/${productId}`);
};

export const removeFavorite = async (
  storeId: string,
  productId: string,
): Promise<void> => {
  await client.delete(`${FAVORITES_BASE}/${storeId}/${productId}`);
};
