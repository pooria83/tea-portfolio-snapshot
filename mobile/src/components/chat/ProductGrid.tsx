import * as React from 'react';
import {StyleSheet, View} from 'react-native';
import {useTranslation} from 'react-i18next';

import {ProductCard} from '../product/ProductCard';
import type {ChatProduct} from '../../features/chat/types';

const COLUMNS = 2;

interface ProductGridProps {
  products: ChatProduct[];
  locale?: string;
  onSelect: (product: ChatProduct) => void;
  onFindSimilar?: (product: ChatProduct) => void;
}

export function ProductGrid({
  products,
  locale,
  onSelect,
  onFindSimilar,
}: ProductGridProps) {
  const {i18n} = useTranslation();
  const uiLocale = i18n.language;
  const effectiveLocale = locale || uiLocale;

  const rows: ChatProduct[][] = [];
  for (let i = 0; i < products.length; i += COLUMNS) {
    rows.push(products.slice(i, i + COLUMNS));
  }

  return (
    <View style={styles.grid}>
      {rows.map((row, rowIndex) => (
        <View key={`row-${rowIndex}`} style={styles.row}>
          {row.map((product) => (
            <ProductCard
              key={product.id}
              product={product}
              locale={effectiveLocale}
              onSelect={(selected) => onSelect(selected as ChatProduct)}
              {...(onFindSimilar
                ? {
                    onFindSimilar: (selected) =>
                      onFindSimilar(selected as ChatProduct),
                  }
                : {})}
            />
          ))}
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  grid: {
    width: '100%',
    gap: 8,
  },
  row: {
    flexDirection: 'row',
    gap: 8,
    alignItems: 'stretch',
  },
});
