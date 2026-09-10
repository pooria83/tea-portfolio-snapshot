import {render, userEvent} from '@testing-library/react-native';
import {PaperProvider, MD3LightTheme} from 'react-native-paper';
import * as React from 'react';
import {ProductGrid} from '../../../src/components/chat/ProductGrid';
import type {ChatProduct} from '../../../src/features/chat/types';

const wrapper = ({children}: {children: React.ReactNode}) => (
  <PaperProvider theme={MD3LightTheme}>{children}</PaperProvider>
);

const product: ChatProduct = {
  id: 'p-1',
  name: 'Red Dress',
  name_ar: 'فستان أحمر',
  name_fa: 'لباس قرمز',
  name_en: 'Red Dress',
  price: 129.5,
  currency: 'SAR',
  brand: 'Zara',
  brand_ar: 'زارا',
  brand_en: 'Zara',
  image_url: 'https://portfolio.example.invalid/product-graph/dress.jpg',
  buy_url: null,
  store_id: 'store-1',
};

describe('ProductGrid', () => {
  it('shows the localized name for the explicit locale', async () => {
    const onSelect = jest.fn();
    const {getByText} = await render(
      <ProductGrid products={[product]} locale="ar" onSelect={onSelect} />,
      {wrapper},
    );

    expect(getByText('فستان أحمر')).toBeTruthy();
    expect(getByText('زارا')).toBeTruthy();
    expect(getByText('129.5 SAR')).toBeTruthy();
  });

  it('prefers the message locale over the app language', async () => {
    const {getByText} = await render(
      <ProductGrid products={[product]} locale="fa" onSelect={jest.fn()} />,
      {wrapper},
    );

    expect(getByText('لباس قرمز')).toBeTruthy();
  });

  it('falls back to the app language when no locale is provided', async () => {
    const {getByText} = await render(
      <ProductGrid products={[product]} onSelect={jest.fn()} />,
      {wrapper},
    );

    expect(getByText('Red Dress')).toBeTruthy();
  });

  it('hides the price when it is null', async () => {
    const {queryByText} = await render(
      <ProductGrid
        products={[{...product, price: null}]}
        onSelect={jest.fn()}
      />,
      {wrapper},
    );

    expect(queryByText('null SAR')).toBeNull();
  });

  it('fires onSelect when a product card is pressed', async () => {
    const onSelect = jest.fn();
    const user = userEvent.setup();
    const {getByText} = await render(
      <ProductGrid products={[product]} onSelect={onSelect} />,
      {wrapper},
    );

    await user.press(getByText('Red Dress'));
    expect(onSelect).toHaveBeenCalledWith(product);
  });

  it('fires onFindSimilar with the product when the similar button is pressed', async () => {
    const onFindSimilar = jest.fn();
    const user = userEvent.setup();
    const {getByLabelText} = await render(
      <ProductGrid
        products={[product]}
        onSelect={jest.fn()}
        onFindSimilar={onFindSimilar}
      />,
      {wrapper},
    );

    await user.press(getByLabelText('findSimilar'));
    expect(onFindSimilar).toHaveBeenCalledWith(product);
  });

  it('renders no similar button without onFindSimilar', async () => {
    const {queryByLabelText} = await render(
      <ProductGrid products={[product]} onSelect={jest.fn()} />,
      {wrapper},
    );

    expect(queryByLabelText('findSimilar')).toBeNull();
  });
});
