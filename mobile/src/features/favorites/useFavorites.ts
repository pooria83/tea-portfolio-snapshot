import {useMutation, useQuery, useQueryClient} from '@tanstack/react-query';

import {classifyError} from '../../services/api/errors';
import {log} from '../../services/logging/logger';
import {addFavorite, fetchFavorites, removeFavorite} from './favoritesApi';
import type {FavoriteProduct} from './types';

export const FAVORITES_QUERY_KEY = ['favorites'];

export const useGetFavoritesQuery = () =>
  useQuery({
    queryKey: FAVORITES_QUERY_KEY,
    queryFn: fetchFavorites,
  });

export const useAddFavoriteMutation = () => {
  const queryClient = useQueryClient();
  const {data} = useGetFavoritesQuery();

  return useMutation({
    mutationFn: ({storeId, productId}: {storeId: string; productId: string}) =>
      addFavorite(storeId, productId),
    onMutate: ({storeId, productId}) => {
      // When re-adding after an optimistic remove, restore the removed entry.
      const previous =
        queryClient.getQueryData<FavoriteProduct[]>(FAVORITES_QUERY_KEY);
      const removed = data?.filter(
        (item) => item.store_id === storeId && item.id === productId,
      );
      // Re-adding is only meaningful for items already in the canonical list;
      // brand-new products are inserted after the request via invalidation.
      if (previous && removed?.length) {
        void queryClient.setQueryData(FAVORITES_QUERY_KEY, [
          ...previous,
          ...removed,
        ]);
      }
      return {previous};
    },
    onError: (error: unknown, _variables, context) => {
      log.warn('addFavorite failed', classifyError(error));
      if (context?.previous) {
        void queryClient.setQueryData(FAVORITES_QUERY_KEY, context.previous);
      }
    },
    onSettled: () => {
      void queryClient.invalidateQueries({queryKey: FAVORITES_QUERY_KEY});
    },
  });
};

export const useRemoveFavoriteMutation = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({storeId, productId}: {storeId: string; productId: string}) =>
      removeFavorite(storeId, productId),
    onMutate: ({storeId, productId}) => {
      const previous =
        queryClient.getQueryData<FavoriteProduct[]>(FAVORITES_QUERY_KEY);
      if (previous) {
        void queryClient.setQueryData(
          FAVORITES_QUERY_KEY,
          previous.filter(
            (item) => !(item.store_id === storeId && item.id === productId),
          ),
        );
      }
      return {previous};
    },
    onError: (error: unknown, _variables, context) => {
      log.warn('removeFavorite failed', classifyError(error));
      if (context?.previous) {
        void queryClient.setQueryData(FAVORITES_QUERY_KEY, context.previous);
      }
    },
    onSettled: () => {
      void queryClient.invalidateQueries({queryKey: FAVORITES_QUERY_KEY});
    },
  });
};

/**
 * True when the given product is in the favorites list. Falls back to false
 * while the list is still loading.
 */
export const useIsFavorite = (storeId: string, productId: string): boolean => {
  const {data} = useGetFavoritesQuery();
  return (
    data?.some((item) => item.store_id === storeId && item.id === productId) ??
    false
  );
};
