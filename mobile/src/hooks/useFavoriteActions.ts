import * as React from 'react';
import {useTranslation} from 'react-i18next';

import {
  useAddFavoriteMutation,
  useIsFavorite,
  useRemoveFavoriteMutation,
} from '../features/favorites/useFavorites';
import {useSuccessToastStore} from '../features/feedback/successToastStore';

interface FavoriteActions {
  isFavorite: boolean;
  busy: boolean;
  /** False when the product has no store id — the toggle cannot be used. */
  enabled: boolean;
  confirmVisible: boolean;
  /** Add → save immediately; remove → open the confirmation dialog. */
  toggle: () => void;
  confirmRemove: () => void;
  cancelRemove: () => void;
}

export function useFavoriteActions(
  storeId: string,
  productId: string,
): FavoriteActions {
  const {t} = useTranslation('nav');
  const isFavorite = useIsFavorite(storeId, productId);
  const addMutation = useAddFavoriteMutation();
  const removeMutation = useRemoveFavoriteMutation();
  const showMessage = useSuccessToastStore((state) => state.showMessage);
  const [confirmVisible, setConfirmVisible] = React.useState(false);

  const busy = addMutation.isPending || removeMutation.isPending;
  const enabled = storeId.length > 0 && productId.length > 0;

  const toggle = React.useCallback(() => {
    if (busy || !enabled) {
      return;
    }
    if (isFavorite) {
      setConfirmVisible(true);
      return;
    }
    addMutation.mutate(
      {storeId, productId},
      {
        onSuccess: () => {
          showMessage(t('addedToFavorites'));
        },
      },
    );
  }, [
    busy,
    enabled,
    isFavorite,
    addMutation,
    storeId,
    productId,
    showMessage,
    t,
  ]);

  const confirmRemove = React.useCallback(() => {
    if (busy || !enabled) {
      return;
    }
    setConfirmVisible(false);
    removeMutation.mutate(
      {storeId, productId},
      {
        onSuccess: () => {
          showMessage(t('removedFromFavorites'));
        },
      },
    );
  }, [busy, enabled, removeMutation, storeId, productId, showMessage, t]);

  const cancelRemove = React.useCallback(() => {
    setConfirmVisible(false);
  }, []);

  return {
    isFavorite,
    busy,
    enabled,
    confirmVisible,
    toggle,
    confirmRemove,
    cancelRemove,
  };
}
