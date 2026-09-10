import {render, userEvent, waitFor} from '@testing-library/react-native';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import * as React from 'react';
import {PaperProvider, MD3LightTheme} from 'react-native-paper';

import {ProductViewModal} from '../../src/components/product/ProductViewModal';
import {useSuccessToastStore} from '../../src/features/feedback/successToastStore';

const mockRemoveFavorite = jest.fn();
const mockAddFavorite = jest.fn();

jest.mock('../../src/services/api/client', () => ({
  __esModule: true,
  default: {get: jest.fn(), put: jest.fn(), delete: jest.fn()},
}));

jest.mock('../../src/features/favorites/useFavorites', () => ({
  useGetFavoritesQuery: () => ({
    data: [],
    isLoading: false,
    isError: false,
    refetch: jest.fn(),
  }),
  useAddFavoriteMutation: () => ({
    isPending: false,
    mutate: mockAddFavorite,
  }),
  useRemoveFavoriteMutation: () => ({
    isPending: false,
    mutate: (
      vars: {storeId: string; productId: string},
      options?: {onSuccess?: () => void},
    ) => {
      mockRemoveFavorite(vars);
      options?.onSuccess?.();
    },
  }),
  useIsFavorite: () => true,
}));

const wrapper = ({children}: {children: React.ReactNode}) => (
  <QueryClientProvider
    client={new QueryClient({defaultOptions: {queries: {retry: false}}})}>
    <PaperProvider theme={MD3LightTheme}>{children}</PaperProvider>
  </QueryClientProvider>
);

describe('ProductViewModal favorite actions', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useSuccessToastStore.getState().clearMessage();
  });

  const renderModal = () =>
    render(
      <ProductViewModal
        open
        storeId="store-1"
        productId="prod-1"
        onClose={jest.fn()}
      />,
      {wrapper},
    );

  it('shows the confirmation dialog inside the modal and removes on confirm', async () => {
    const user = userEvent.setup();
    const {getByLabelText, getByTestId, getByText} = await renderModal();

    await user.press(getByLabelText('removeFromFavorites'));

    expect(getByText('removeFavoriteTitle')).toBeTruthy();

    await user.press(getByTestId('confirm-remove-favorite'));

    await waitFor(() => {
      expect(mockRemoveFavorite).toHaveBeenCalledWith({
        storeId: 'store-1',
        productId: 'prod-1',
      });
      expect(useSuccessToastStore.getState().message).toBe(
        'removedFromFavorites',
      );
    });
  });
});
