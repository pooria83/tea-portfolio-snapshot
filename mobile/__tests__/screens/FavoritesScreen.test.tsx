import {render, userEvent, waitFor} from '@testing-library/react-native';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import * as React from 'react';
import {PaperProvider, MD3LightTheme} from 'react-native-paper';

import FavoritesScreen from '../../src/app/screens/FavoritesScreen';

const MOCK_PRODUCTS = [
  {
    id: 'prod-1',
    store_id: 'store-1',
    store_name: 'Store One',
    name_ar: null,
    name_en: 'Wool Sweater',
    name_fa: null,
    brand: 'BrandX',
    price: 120,
    original_price: null,
    sale_price: null,
    currency: 'SAR',
    image_url: null,
    created_at: '2026-08-11T00:00:00Z',
  },
];

const mockRemoveFavorite = jest.fn();

jest.mock('../../src/features/favorites/useFavorites', () => ({
  useGetFavoritesQuery: () => ({
    data: MOCK_PRODUCTS,
    isLoading: false,
    isError: false,
    refetch: jest.fn(),
  }),
  useAddFavoriteMutation: () => ({
    isPending: false,
    mutate: jest.fn(),
  }),
  useRemoveFavoriteMutation: () => ({
    isPending: false,
    mutate: mockRemoveFavorite,
  }),
  useIsFavorite: () => true,
}));

const wrapper = ({children}: {children: React.ReactNode}) => (
  <QueryClientProvider client={new QueryClient()}>
    <PaperProvider theme={MD3LightTheme}>{children}</PaperProvider>
  </QueryClientProvider>
);

describe('FavoritesScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('lists saved products with a bookmark control', async () => {
    const {getByText, getByLabelText} = await render(<FavoritesScreen />, {
      wrapper,
    });

    expect(getByText('Wool Sweater')).toBeTruthy();
    expect(getByLabelText('removeFromFavorites')).toBeTruthy();
  });

  it('requires confirmation before removing and removes after confirm', async () => {
    const user = userEvent.setup();
    const {getByLabelText, getByText, getByTestId} = await render(
      <FavoritesScreen />,
      {wrapper},
    );

    await user.press(getByLabelText('removeFromFavorites'));

    expect(getByText('removeFavoriteTitle')).toBeTruthy();
    expect(getByText('removeFavoriteMessage')).toBeTruthy();
    expect(mockRemoveFavorite).not.toHaveBeenCalled();

    await user.press(getByTestId('confirm-remove-favorite'));

    await waitFor(() => {
      expect(mockRemoveFavorite).toHaveBeenCalledWith(
        {storeId: 'store-1', productId: 'prod-1'},
        expect.anything(),
      );
    });
  });

  it('cancels the removal dialog without removing', async () => {
    const user = userEvent.setup();
    const {getByLabelText, getByText, queryByText} = await render(
      <FavoritesScreen />,
      {wrapper},
    );

    await user.press(getByLabelText('removeFromFavorites'));
    await user.press(getByText('cancel', {exact: false}));

    await waitFor(() => {
      expect(queryByText('removeFavoriteTitle')).toBeNull();
      expect(mockRemoveFavorite).not.toHaveBeenCalled();
    });
  });
});
