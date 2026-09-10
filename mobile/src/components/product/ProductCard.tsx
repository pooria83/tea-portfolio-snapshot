import * as React from 'react';
import {Pressable, StyleSheet, Text, View} from 'react-native';
import {useTheme} from 'react-native-paper';
import {useTranslation} from 'react-i18next';
import MaterialIcons from 'react-native-vector-icons/MaterialIcons';

import {localeValue} from '../../features/chat/locale';
import {RetryingThumbnail} from '../chat/RetryingThumbnail';

/**
 * Minimal product shape shared by chat results and saved favorites. Both
 * ChatProduct and FavoriteProduct satisfy it structurally.
 */
export interface CardProduct {
  id: string;
  name?: string | null;
  name_ar?: string | null;
  name_en?: string | null;
  name_fa?: string | null;
  price?: number | null;
  currency?: string | null;
  brand?: string | null;
  brand_ar?: string | null;
  brand_en?: string | null;
  brand_fa?: string | null;
  image_url?: string | null;
}

interface ProductCardProps {
  product: CardProduct;
  locale?: string;
  onSelect: (product: CardProduct) => void;
  /** When set, renders the bookmark toggle overlay. */
  isFavorite?: boolean;
  /** Toggling immediately performs the mutation; no local state needed. */
  onToggleFavorite?: () => void;
  favoriteBusy?: boolean;
  /** When set, renders the "find similar" overlay button. */
  onFindSimilar?: (product: CardProduct) => void;
}

export function ProductCard({
  product,
  locale,
  onSelect,
  isFavorite,
  onToggleFavorite,
  favoriteBusy,
  onFindSimilar,
}: ProductCardProps) {
  const {i18n} = useTranslation();
  const theme = useTheme();
  const effectiveLocale = locale ?? i18n.language;

  const displayName =
    localeValue(
      effectiveLocale,
      product.name_ar ?? '',
      product.name_fa ?? '',
      product.name_en ?? '',
    ) ||
    product.name ||
    '—';
  const displayBrand =
    localeValue(
      effectiveLocale,
      product.brand_ar ?? '',
      product.brand_fa ?? '',
      product.brand_en ?? '',
    ) || product.brand;

  return (
    <Pressable
      onPress={() => onSelect(product)}
      style={({pressed}) => [
        styles.card,
        {
          backgroundColor: theme.colors.surface,
          borderColor: theme.colors.outlineVariant,
        },
        pressed && {backgroundColor: theme.colors.surfaceVariant},
      ]}>
      <View style={styles.thumbWrap}>
        {product.image_url ? (
          <View
            style={[
              styles.thumb,
              {backgroundColor: theme.colors.surfaceVariant},
            ]}>
            <RetryingThumbnail
              src={product.image_url}
              alt={displayName}
              style={styles.thumbFill}
            />
          </View>
        ) : (
          <View
            style={[
              styles.thumb,
              {backgroundColor: theme.colors.surfaceVariant},
            ]}
          />
        )}
        {onToggleFavorite ? (
          <View style={styles.favoriteOverlay}>
            <FavoriteButton
              isFavorite={isFavorite === true}
              onPress={onToggleFavorite}
              busy={favoriteBusy === true}
            />
          </View>
        ) : null}
        {onFindSimilar ? (
          <View style={styles.similarOverlay}>
            <SimilarButton onPress={() => onFindSimilar(product)} />
          </View>
        ) : null}
      </View>
      <View style={styles.info}>
        <Text
          style={[styles.name, {color: theme.colors.onSurface}]}
          numberOfLines={2}>
          {displayName}
        </Text>
        {displayBrand ? (
          <Text
            style={[styles.brand, {color: theme.colors.onSurfaceVariant}]}
            numberOfLines={1}>
            {displayBrand}
          </Text>
        ) : null}
        {product.price != null ? (
          <Text style={[styles.price, {color: theme.colors.onSurface}]}>
            {product.price} {product.currency}
          </Text>
        ) : null}
      </View>
    </Pressable>
  );
}

function FavoriteButton({
  isFavorite,
  onPress,
  busy,
}: {
  isFavorite: boolean;
  onPress: () => void;
  busy: boolean;
}) {
  const {t} = useTranslation('nav');
  const theme = useTheme();

  return (
    <Pressable
      onPress={onPress}
      disabled={busy}
      hitSlop={8}
      accessibilityRole="button"
      accessibilityLabel={
        isFavorite ? t('removeFromFavorites') : t('addToFavorites')
      }
      style={[styles.favoriteButton, {opacity: busy ? 0.6 : 1}]}>
      <MaterialIcons
        name={isFavorite ? 'bookmark' : 'bookmark-border'}
        size={24}
        color={isFavorite ? theme.colors.primary : '#FFFFFF'}
      />
    </Pressable>
  );
}

function SimilarButton({onPress}: {onPress: () => void}) {
  const {t} = useTranslation('chat');
  const theme = useTheme();

  return (
    <Pressable
      onPress={onPress}
      hitSlop={8}
      accessibilityRole="button"
      accessibilityLabel={t('findSimilar')}
      style={styles.similarButton}>
      <MaterialIcons
        name="auto-awesome"
        size={20}
        color={theme.colors.primary}
      />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    flex: 1,
    flexDirection: 'column',
    borderWidth: 1,
    borderRadius: 12,
    overflow: 'hidden',
  },
  thumbWrap: {
    width: '100%',
    aspectRatio: 1,
  },
  thumb: {
    width: '100%',
    height: '100%',
  },
  thumbFill: {
    width: '100%',
    height: '100%',
  },
  favoriteOverlay: {
    position: 'absolute',
    top: 4,
    right: 4,
    borderRadius: 999,
    backgroundColor: 'rgba(0, 0, 0, 0.35)',
    overflow: 'hidden',
  },
  similarOverlay: {
    position: 'absolute',
    top: 4,
    left: 4,
    borderRadius: 999,
    backgroundColor: 'rgba(0, 0, 0, 0.35)',
    overflow: 'hidden',
  },
  similarButton: {
    padding: 6,
    backgroundColor: 'rgba(255, 255, 255, 0.85)',
  },
  favoriteButton: {
    padding: 4,
  },
  info: {
    padding: 8,
    gap: 2,
  },
  name: {
    fontSize: 13,
    fontWeight: '500',
  },
  brand: {
    fontSize: 11,
  },
  price: {
    fontSize: 13,
    fontWeight: '600',
    marginTop: 2,
  },
});
