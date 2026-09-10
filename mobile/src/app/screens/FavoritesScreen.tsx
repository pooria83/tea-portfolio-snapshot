import * as React from 'react';
import {ActivityIndicator, FlatList, StyleSheet, View} from 'react-native';
import {Button, Text, useTheme} from 'react-native-paper';
import {useTranslation} from 'react-i18next';
import MaterialIcons from 'react-native-vector-icons/MaterialIcons';

import {ProductCard} from '../../components/product/ProductCard';
import {ProductViewModal} from '../../components/product/ProductViewModal';
import FavoriteRemoveDialog from '../../components/product/FavoriteRemoveDialog';
import {useGetFavoritesQuery} from '../../features/favorites/useFavorites';
import {useFavoriteActions} from '../../hooks/useFavoriteActions';
import type {FavoriteProduct} from '../../features/favorites/types';

function FavoriteRow({product}: {product: FavoriteProduct}) {
  const favorite = useFavoriteActions(product.store_id, product.id);
  const [selected, setSelected] = React.useState(false);

  return (
    <View style={styles.cell}>
      <ProductCard
        product={product}
        isFavorite
        favoriteBusy={favorite.busy}
        onToggleFavorite={favorite.toggle}
        onSelect={() => setSelected(true)}
      />
      <FavoriteRemoveDialog
        visible={favorite.confirmVisible}
        busy={favorite.busy}
        onCancel={favorite.cancelRemove}
        onConfirm={favorite.confirmRemove}
      />
      {selected ? (
        <ProductViewModal
          open
          storeId={product.store_id}
          productId={product.id}
          onClose={() => setSelected(false)}
        />
      ) : null}
    </View>
  );
}

export default function FavoritesScreen() {
  const {t} = useTranslation('nav');
  const theme = useTheme();
  const {data, isLoading, isError, refetch} = useGetFavoritesQuery();

  const products = data ?? [];

  if (isLoading) {
    return (
      <View style={[styles.center, {backgroundColor: theme.colors.background}]}>
        <ActivityIndicator size="large" color={theme.colors.primary} />
      </View>
    );
  }

  if (isError) {
    return (
      <View style={[styles.center, {backgroundColor: theme.colors.background}]}>
        <Text variant="bodyLarge">{t('favoritesError')}</Text>
        <Button
          mode="outlined"
          onPress={() => void refetch()}
          style={styles.retry}>
          {t('retry', {ns: 'common'})}
        </Button>
      </View>
    );
  }

  return (
    <View
      style={[styles.container, {backgroundColor: theme.colors.background}]}>
      <Text variant="headlineMedium" style={styles.title}>
        {t('favorites')}
      </Text>
      <FlatList
        data={products}
        keyExtractor={(item) => `${item.store_id}:${item.id}`}
        numColumns={2}
        columnWrapperStyle={styles.column}
        contentContainerStyle={styles.list}
        ListEmptyComponent={
          <View style={styles.empty}>
            <MaterialIcons
              name="bookmark-border"
              size={48}
              color={theme.colors.onSurfaceVariant}
            />
            <Text
              style={[
                styles.emptyText,
                {color: theme.colors.onSurfaceVariant},
              ]}>
              {t('favoritesEmpty')}
            </Text>
          </View>
        }
        renderItem={({item}) => <FavoriteRow product={item} />}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 16,
  },
  retry: {
    marginTop: 4,
  },
  title: {
    paddingHorizontal: 24,
    paddingTop: 24,
    paddingBottom: 8,
  },
  list: {
    padding: 16,
    gap: 8,
    flexGrow: 1,
  },
  column: {
    gap: 8,
  },
  cell: {
    flex: 1,
  },
  empty: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
    paddingVertical: 48,
  },
  emptyText: {
    fontSize: 14,
  },
});
