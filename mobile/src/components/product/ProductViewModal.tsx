import * as React from 'react';
import {
  Linking,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  View,
} from 'react-native';
import {useQuery} from '@tanstack/react-query';
import {Button, Divider, IconButton, List, useTheme} from 'react-native-paper';
import {useTranslation} from 'react-i18next';
import {SafeAreaView} from 'react-native-safe-area-context';
import MaterialIcons from 'react-native-vector-icons/MaterialIcons';

import client from '../../services/api/client';
import {unwrapEnvelope} from '../../services/api/envelope';
import {localeValue} from '../../features/chat/locale';
import {useFavoriteActions} from '../../hooks/useFavoriteActions';
import {RetryingThumbnail} from '../chat/RetryingThumbnail';
import ErrorToast from '../feedback/ErrorToast';
import SuccessToast from '../feedback/SuccessToast';
import FavoriteRemoveDialog from './FavoriteRemoveDialog';
import type {
  AttributeItem,
  ProductImageItem,
  ProductResponse,
  ProductVariantResponse,
} from '../../types/product';

interface ProductViewModalProps {
  open: boolean;
  storeId: string;
  productId: string;
  onClose: () => void;
}

const fetchProduct = async (
  storeId: string,
  productId: string,
): Promise<ProductResponse> => {
  const response = await client.get(`/stores/${storeId}/products/${productId}`);
  return unwrapEnvelope<ProductResponse>(response);
};

const fetchAttributes = async (
  productTypeId: string,
): Promise<AttributeItem[]> => {
  const response = await client.get(
    `/products/attributes?product_type_id=${productTypeId}`,
  );
  return unwrapEnvelope<AttributeItem[]>(response);
};

const formatPrice = (value: number): string => {
  const amount = Number(value);
  if (!Number.isFinite(amount)) {
    return '—';
  }
  return amount.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
};

interface ProductViewProps {
  storeId: string;
  productId: string;
}

export function ProductView({storeId, productId}: ProductViewProps) {
  const {i18n} = useTranslation();
  const {t} = useTranslation('chat');
  const theme = useTheme();
  const locale = i18n.language;

  const {
    data: product,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['product', storeId, productId],
    queryFn: () => fetchProduct(storeId, productId),
  });

  const {data: attributes = []} = useQuery({
    queryKey: ['product-attributes', product?.product_type_id ?? ''],
    queryFn: () => fetchAttributes(product?.product_type_id ?? ''),
    enabled: product?.product_type_id != null,
  });

  const {enAttrMap, arAttrMap, enOptionMap, arOptionMap} = React.useMemo(() => {
    const enAttr = new Map<string, string>();
    const arAttr = new Map<string, string>();
    const enOpt = new Map<string, string>();
    const arOpt = new Map<string, string>();
    for (const attr of attributes) {
      enAttr.set(attr.id, attr.name_en);
      arAttr.set(attr.id, attr.name_ar || '');
      for (const opt of attr.options) {
        enOpt.set(opt.id, opt.value_en);
        arOpt.set(opt.id, opt.value_ar || '');
      }
    }
    for (const av of product?.attribute_values ?? []) {
      const av2 = av as {
        attribute?: {
          name_ar?: string;
          name_en?: string;
          name_fa?: string;
          options?: Array<{
            id: string;
            value_ar?: string;
            value_en?: string;
            value_fa?: string;
          }>;
        };
      };
      const attrData = av2.attribute;
      if (attrData && attrData.name_en) {
        if (!enAttr.has(av.attribute_id)) {
          enAttr.set(av.attribute_id, attrData.name_en);
          arAttr.set(av.attribute_id, attrData.name_ar ?? '');
        }
        for (const opt of attrData.options ?? []) {
          if (opt.id && !enOpt.has(opt.id) && opt.value_en) {
            enOpt.set(opt.id, opt.value_en);
            arOpt.set(opt.id, opt.value_ar ?? '');
          }
        }
      }
    }
    return {
      enAttrMap: enAttr,
      arAttrMap: arAttr,
      enOptionMap: enOpt,
      arOptionMap: arOpt,
    };
  }, [attributes, product?.attribute_values]);

  const groupedAttributes = React.useMemo(() => {
    return (product?.attribute_values ?? []).reduce(
      (acc, av) => {
        const existing = acc.find(
          (entry) => entry.attribute_id === av.attribute_id,
        );
        if (existing) {
          existing.values.push(av.value);
        } else {
          acc.push({...av, values: [av.value]});
        }
        return acc;
      },
      [] as Array<{
        id: string;
        attribute_id: string;
        value: string | null;
        values: (string | null)[];
      }>,
    );
  }, [product?.attribute_values]);

  const [showInactiveVariants, setShowInactiveVariants] = React.useState(false);
  const [selectedColorId, setSelectedColorId] = React.useState<string | null>(
    null,
  );

  const colorOptions = React.useMemo(() => {
    if (!product?.variants) {
      return [];
    }
    const seen = new Set<string>();
    return product.variants.reduce<
      Array<{
        option: (typeof product.variants)[0]['attribute_options'][0];
        variantIds: string[];
      }>
    >((acc, v) => {
      for (const opt of v.attribute_options || []) {
        if (opt.color_hex && !seen.has(opt.id)) {
          seen.add(opt.id);
          const variantIds = (product.variants ?? [])
            .filter((v2) => v2.attribute_options?.some((o) => o.id === opt.id))
            .map((v2) => v2.id);
          acc.push({option: opt, variantIds});
        }
      }
      return acc;
    }, []);
  }, [product]);

  const activeColorId = selectedColorId ?? colorOptions[0]?.option.id ?? null;
  const selectedColor = colorOptions.find((c) => c.option.id === activeColorId);

  const filteredImages = React.useMemo(() => {
    const allImages = product?.images || [];
    if (!selectedColor || !activeColorId) {
      return allImages;
    }
    const variantIds = new Set(selectedColor.variantIds);
    const seen = new Set<string>();
    return allImages.filter((img) => {
      if (!img.variant_id) {
        return false;
      }
      if (!variantIds.has(img.variant_id)) {
        return false;
      }
      if (seen.has(img.image_url)) {
        return false;
      }
      seen.add(img.image_url);
      return true;
    });
  }, [product?.images, selectedColor, activeColorId]);

  const resolveValue = (
    value: string | null,
    optionMap: Map<string, string>,
  ): string => {
    if (!value) {
      return '—';
    }
    try {
      const parsed = JSON.parse(value) as unknown;
      if (Array.isArray(parsed)) {
        if (
          parsed.length > 0 &&
          typeof parsed[0] === 'object' &&
          parsed[0] !== null &&
          'material' in parsed[0]
        ) {
          return parsed
            .map((entry: unknown) => {
              const materialEntry = entry as {
                material?: unknown;
                percentage?: unknown;
              };
              const material =
                typeof materialEntry.material === 'string'
                  ? materialEntry.material
                  : '';
              const percentage =
                typeof materialEntry.percentage === 'number'
                  ? materialEntry.percentage
                  : 0;
              return `${
                optionMap.get(material) ?? material.slice(0, 8)
              } ${percentage}%`;
            })
            .join(', ');
        }
        return parsed
          .map((id: unknown) => (typeof id === 'string' ? id : ''))
          .filter((id: string) => id.length > 0)
          .map((id: string) => optionMap.get(id) ?? id.slice(0, 8))
          .join(', ');
      }
    } catch {
      // fall through to plain option resolution
    }
    return optionMap.get(value) ?? value.slice(0, 8);
  };

  if (isLoading) {
    return <ProductViewSkeleton />;
  }
  if (error || !product) {
    return (
      <View style={styles.notFound}>
        <MaterialIcons
          name="inventory-2"
          size={48}
          color={theme.colors.onSurfaceVariant}
        />
        <Text
          style={[styles.notFoundText, {color: theme.colors.onSurfaceVariant}]}>
          {t('productNotFound')}
        </Text>
      </View>
    );
  }

  const name = product.name_en ?? '';
  const nameAr = product.name_ar ?? '';
  const shortDesc = product.short_description_en ?? '';
  const shortDescAr = product.short_description_ar ?? '';
  const longDesc = product.long_description_en ?? '';
  const longDescAr = product.long_description_ar ?? '';
  const hasSale = product.sale_price != null && product.original_price != null;
  const displayPrice = hasSale ? product.sale_price : product.price;
  const currency = product.currency || 'SAR';

  const visibleVariants = showInactiveVariants
    ? product.variants
    : product.variants?.filter((v) => v.is_active);
  const totalVariants = product.variants?.length ?? 0;
  const activeVariants =
    product.variants?.filter((v) => v.is_active).length ?? 0;
  const inactiveCount = totalVariants - activeVariants;

  const openSourceLink = () => {
    if (product.source_url) {
      void Linking.openURL(product.source_url);
    }
  };

  return (
    <ScrollView contentContainerStyle={styles.productContent}>
      <ImageGallery
        images={filteredImages}
        name={name || 'Product'}
        colorOptions={colorOptions}
        selectedColorId={activeColorId}
        onSelectColor={setSelectedColorId}
      />

      <View style={styles.infoBlock}>
        <View style={styles.badgeRow}>
          <View
            style={[
              styles.statusBadge,
              {
                backgroundColor:
                  product.status === 'active'
                    ? theme.colors.primaryContainer
                    : theme.colors.surfaceVariant,
              },
            ]}>
            <Text
              style={[
                styles.statusBadgeText,
                {
                  color:
                    product.status === 'active'
                      ? theme.colors.onPrimaryContainer
                      : theme.colors.onSurfaceVariant,
                },
              ]}>
              {product.status}
            </Text>
          </View>
          <View style={styles.createdRow}>
            <MaterialIcons
              name="calendar-today"
              size={12}
              color={theme.colors.onSurfaceVariant}
            />
            <Text
              style={[
                styles.createdText,
                {color: theme.colors.onSurfaceVariant},
              ]}>
              {new Date(product.created_at).toLocaleDateString()}
            </Text>
          </View>
        </View>

        <Text style={[styles.name, {color: theme.colors.onSurface}]}>
          {name}
        </Text>
        {nameAr ? (
          <Text style={[styles.nameAr, {color: theme.colors.onSurfaceVariant}]}>
            {nameAr}
          </Text>
        ) : null}

        {product.brand_name ? (
          <Text style={[styles.brand, {color: theme.colors.onSurfaceVariant}]}>
            {product.brand_name}
          </Text>
        ) : null}

        {product.source_url ? (
          <Pressable onPress={openSourceLink} style={styles.sourceLink}>
            <MaterialIcons
              name="open-in-new"
              size={16}
              color={theme.colors.primary}
            />
            <Text
              style={[styles.sourceLinkText, {color: theme.colors.primary}]}>
              {t('openSourceLink')}
            </Text>
          </Pressable>
        ) : null}

        <View style={styles.priceRow}>
          {displayPrice == null ? (
            <Text
              style={[
                styles.priceNotSet,
                {color: theme.colors.onSurfaceVariant},
              ]}>
              {t('priceNotSet')}
            </Text>
          ) : (
            <>
              <Text style={[styles.price, {color: theme.colors.onSurface}]}>
                {formatPrice(displayPrice)}
              </Text>
              <Text
                style={[
                  styles.currency,
                  {color: theme.colors.onSurfaceVariant},
                ]}>
                {currency}
              </Text>
            </>
          )}
          {hasSale ? (
            <>
              <Text
                style={[
                  styles.originalPrice,
                  {color: theme.colors.onSurfaceVariant},
                ]}>
                {formatPrice(product.original_price ?? 0)}
              </Text>
              <View
                style={[
                  styles.discountBadge,
                  {backgroundColor: theme.colors.errorContainer},
                ]}>
                <Text
                  style={[
                    styles.discountText,
                    {color: theme.colors.onErrorContainer},
                  ]}>
                  -
                  {Math.round(
                    (1 -
                      (product.sale_price ?? 0) /
                        (product.original_price ?? 1)) *
                      100,
                  )}
                  %
                </Text>
              </View>
            </>
          ) : null}
        </View>

        <Text style={[styles.stock, {color: theme.colors.onSurfaceVariant}]}>
          {t('stock')}: {product.quantity}
          {product.has_variants ? ` (${t('managedViaVariants')})` : ''}
        </Text>

        {shortDesc ? (
          <Text
            style={[
              styles.description,
              {color: theme.colors.onSurfaceVariant},
            ]}>
            {shortDesc}
          </Text>
        ) : null}
        {shortDescAr ? (
          <Text
            style={[
              styles.description,
              {color: theme.colors.onSurfaceVariant},
            ]}>
            {shortDescAr}
          </Text>
        ) : null}

        <Divider style={styles.divider} />
        <MetaRow label={t('collection')} value={product.collection} />
        {product.collection_ar ? (
          <MetaRow label={t('collectionAr')} value={product.collection_ar} />
        ) : null}
        <MetaRow
          label={t('hasVariants')}
          value={product.has_variants ? t('yes') : t('no')}
        />
        {product.is_multi_piece ? (
          <MetaRow
            label={t('pieces')}
            value={
              product.pieces
                ?.map((p) => p.name_en)
                .filter(Boolean)
                .join(', ') || t('yes')
            }
          />
        ) : null}
      </View>

      {longDesc ? (
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, {color: theme.colors.onSurface}]}>
            {t('description')}
          </Text>
          <Text
            style={[
              styles.sectionBody,
              {color: theme.colors.onSurfaceVariant},
            ]}>
            {longDesc}
          </Text>
        </View>
      ) : null}
      {longDescAr ? (
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, {color: theme.colors.onSurface}]}>
            {t('descriptionAr')}
          </Text>
          <Text
            style={[
              styles.sectionBody,
              {color: theme.colors.onSurfaceVariant},
            ]}>
            {longDescAr}
          </Text>
        </View>
      ) : null}

      {product.is_multi_piece && product.pieces && product.pieces.length > 0 ? (
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, {color: theme.colors.onSurface}]}>
            {t('pieces')}
          </Text>
          <View style={styles.chipsRow}>
            {product.pieces.map((piece) => (
              <View
                key={piece.id}
                style={[
                  styles.chip,
                  {backgroundColor: theme.colors.surfaceVariant},
                ]}>
                <Text
                  style={[styles.chipText, {color: theme.colors.onSurface}]}>
                  {piece.name_en || 'Unnamed'}
                </Text>
              </View>
            ))}
          </View>
        </View>
      ) : null}

      {product.is_multi_piece &&
      product.color_sets &&
      product.color_sets.length > 0 ? (
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, {color: theme.colors.onSurface}]}>
            {t('colorSets')} ({product.color_sets.length})
          </Text>
          <View style={styles.colorSets}>
            {product.color_sets.map((cs) => (
              <View
                key={cs.id}
                style={[
                  styles.colorSetCard,
                  {backgroundColor: theme.colors.surfaceVariant},
                ]}>
                {cs.values.map((val) => (
                  <View key={val.id} style={styles.colorSetValue}>
                    {val.color_option?.color_hex ? (
                      <View
                        style={[
                          styles.colorDot,
                          {backgroundColor: val.color_option.color_hex},
                        ]}
                      />
                    ) : null}
                    <View>
                      <Text
                        style={[
                          styles.chipText,
                          {color: theme.colors.onSurface},
                        ]}>
                        {val.piece_name_en || 'Piece'}
                      </Text>
                      <Text
                        style={[
                          styles.colorSetName,
                          {color: theme.colors.onSurfaceVariant},
                        ]}>
                        {val.color_option
                          ? localeValue(
                              locale,
                              val.color_option.value_ar,
                              val.color_option.value_fa,
                              val.color_option.value_en,
                            )
                          : '—'}
                      </Text>
                    </View>
                  </View>
                ))}
              </View>
            ))}
          </View>
        </View>
      ) : null}

      {product.variants && product.variants.length > 0 ? (
        <View style={styles.section}>
          <View style={styles.variantsHeader}>
            <Text
              style={[styles.sectionTitle, {color: theme.colors.onSurface}]}>
              {t('variants')} ({visibleVariants.length}/{totalVariants})
            </Text>
            {inactiveCount > 0 ? (
              <View style={styles.inactiveToggle}>
                <Text
                  style={[
                    styles.inactiveLabel,
                    {color: theme.colors.onSurfaceVariant},
                  ]}>
                  {t('showInactive')}
                </Text>
                <Switch
                  value={showInactiveVariants}
                  onValueChange={setShowInactiveVariants}
                />
              </View>
            ) : null}
          </View>
          <View style={styles.variantsGrid}>
            {visibleVariants.map((v) => (
              <VariantCard key={v.id} variant={v} currencyCode={currency} />
            ))}
          </View>
        </View>
      ) : null}

      {product.attribute_values && product.attribute_values.length > 0 ? (
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, {color: theme.colors.onSurface}]}>
            {t('attributes')}
          </Text>
          <List.Section>
            <List.Accordion title={t('attributesEnglish')}>
              {groupedAttributes.map((av) => (
                <View key={av.id} style={styles.attrRow}>
                  <Text
                    style={[
                      styles.attrLabel,
                      {color: theme.colors.onSurfaceVariant},
                    ]}>
                    {enAttrMap.get(av.attribute_id) ??
                      av.attribute_id.slice(0, 8)}
                    :
                  </Text>
                  <Text
                    style={[styles.attrValue, {color: theme.colors.onSurface}]}>
                    {av.values
                      .map((v) => resolveValue(v, enOptionMap))
                      .join(', ')}
                  </Text>
                </View>
              ))}
            </List.Accordion>
            <List.Accordion title={t('attributesArabic')}>
              {groupedAttributes.map((av) => (
                <View key={av.id} style={styles.attrRow}>
                  <Text
                    style={[
                      styles.attrLabel,
                      {color: theme.colors.onSurfaceVariant},
                    ]}>
                    {arAttrMap.get(av.attribute_id) ||
                      enAttrMap.get(av.attribute_id) ||
                      av.attribute_id.slice(0, 8)}
                    :
                  </Text>
                  <Text
                    style={[styles.attrValue, {color: theme.colors.onSurface}]}>
                    {av.values
                      .map((v) => resolveValue(v, arOptionMap))
                      .join('، ')}
                  </Text>
                </View>
              ))}
            </List.Accordion>
          </List.Section>
        </View>
      ) : null}

      {product.sizes && product.sizes.length > 0 ? (
        <View style={styles.section}>
          <Text style={[styles.sectionTitle, {color: theme.colors.onSurface}]}>
            {t('sizes')}
          </Text>
          <View style={styles.chipsRow}>
            {product.sizes.map((s) => (
              <View
                key={s.id}
                style={[
                  styles.chip,
                  {backgroundColor: theme.colors.surfaceVariant},
                ]}>
                <Text
                  style={[styles.chipText, {color: theme.colors.onSurface}]}>
                  {s.size_label}{' '}
                  <Text style={{color: theme.colors.onSurfaceVariant}}>
                    ({s.stock})
                  </Text>
                </Text>
              </View>
            ))}
          </View>
        </View>
      ) : null}

      <View style={styles.footerMeta}>
        <Text
          style={[styles.footerText, {color: theme.colors.onSurfaceVariant}]}>
          {t('id')}: {product.id}
        </Text>
        <Text
          style={[styles.footerText, {color: theme.colors.onSurfaceVariant}]}>
          {t('updated')}: {new Date(product.updated_at).toLocaleString()}
        </Text>
      </View>
    </ScrollView>
  );
}

function ImageGallery({
  images,
  name,
  colorOptions,
  selectedColorId,
  onSelectColor,
}: {
  images: ProductImageItem[];
  name: string;
  colorOptions: Array<{
    option: {
      id: string;
      color_hex?: string | null;
      value_en?: string;
      value_ar?: string;
      value_fa?: string;
    };
    variantIds: string[];
  }>;
  selectedColorId: string | null;
  onSelectColor: (id: string | null) => void;
}) {
  const {i18n} = useTranslation();
  const theme = useTheme();
  const locale = i18n.language;
  const [selected, setSelected] = React.useState(0);

  if (images.length === 0) {
    return (
      <View
        style={[
          styles.galleryEmpty,
          {backgroundColor: theme.colors.surfaceVariant},
        ]}>
        <MaterialIcons
          name="photo"
          size={64}
          color={theme.colors.onSurfaceVariant}
        />
      </View>
    );
  }

  const current = images[selected];
  if (!current) {
    return null;
  }

  return (
    <View style={styles.gallery}>
      <View
        style={[
          styles.mainImage,
          {backgroundColor: theme.colors.surfaceVariant},
        ]}>
        <RetryingThumbnail
          src={current.image_url}
          alt={current.alt_text_en || name}
          style={styles.mainImageContent}
          resizeMode="contain"
          optimizedWidth={1080}
        />
      </View>

      {colorOptions.length > 1 ? (
        <View style={styles.colorChips}>
          {colorOptions.map((c) => (
            <Pressable
              key={c.option.id}
              onPress={() => {
                const next =
                  c.option.id === selectedColorId ? null : c.option.id;
                onSelectColor(next);
                setSelected(0);
              }}
              style={[
                styles.colorChip,
                {
                  backgroundColor: theme.colors.surfaceVariant,
                  borderColor:
                    c.option.id === selectedColorId
                      ? theme.colors.primary
                      : 'transparent',
                },
              ]}>
              {c.option.color_hex ? (
                <View
                  style={[
                    styles.colorChipDot,
                    {backgroundColor: c.option.color_hex},
                  ]}
                />
              ) : null}
              <Text
                style={[styles.colorChipText, {color: theme.colors.onSurface}]}>
                {localeValue(
                  locale,
                  c.option.value_ar ?? '',
                  c.option.value_fa ?? '',
                  c.option.value_en ?? '',
                )}
              </Text>
            </Pressable>
          ))}
        </View>
      ) : null}

      {images.length > 1 ? (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.thumbnails}>
          {images.map((img, i) => (
            <Pressable
              key={img.id}
              onPress={() => setSelected(i)}
              style={[
                styles.thumbButton,
                {
                  borderColor:
                    i === selected ? theme.colors.primary : 'transparent',
                },
              ]}>
              <RetryingThumbnail
                src={img.image_url}
                alt={img.alt_text_en || `${name} ${i + 1}`}
                style={styles.thumbImage}
              />
            </Pressable>
          ))}
        </ScrollView>
      ) : null}
    </View>
  );
}

function VariantCard({
  variant,
  currencyCode,
}: {
  variant: ProductVariantResponse;
  currencyCode: string;
}) {
  const {i18n} = useTranslation();
  const theme = useTheme();
  const locale = i18n.language;

  const colorCircleStyle = (colorHex: string | null) => {
    if (colorHex === '#FF00FF') {
      return {
        backgroundColor: theme.colors.surfaceVariant,
      };
    }
    return {backgroundColor: colorHex || '#ccc'};
  };

  return (
    <View
      style={[
        styles.variantCard,
        {
          backgroundColor: variant.is_active
            ? theme.colors.surface
            : theme.colors.surfaceVariant,
          borderColor: theme.colors.outlineVariant,
        },
        !variant.is_active && styles.variantInactive,
      ]}>
      <View style={styles.variantHeader}>
        <Text style={[styles.variantSku, {color: theme.colors.onSurface}]}>
          {variant.sku}
        </Text>
        <View
          style={[
            styles.statusBadge,
            {
              backgroundColor: variant.is_active
                ? theme.colors.primaryContainer
                : theme.colors.surfaceVariant,
            },
          ]}>
          <Text
            style={[
              styles.statusBadgeText,
              {
                color: variant.is_active
                  ? theme.colors.onPrimaryContainer
                  : theme.colors.onSurfaceVariant,
              },
            ]}>
            {variant.is_active ? 'Active' : 'Inactive'}
          </Text>
        </View>
      </View>
      {variant.attribute_options && variant.attribute_options.length > 0 ? (
        <View style={styles.variantChips}>
          {variant.attribute_options.map((opt) => (
            <View
              key={opt.id}
              style={[
                styles.optionChip,
                {backgroundColor: theme.colors.surfaceVariant},
              ]}>
              {opt.color_hex ? (
                <View
                  style={[styles.optionDot, {backgroundColor: opt.color_hex}]}
                />
              ) : null}
              <Text
                style={[
                  styles.optionChipText,
                  {color: theme.colors.onSurface},
                ]}>
                {localeValue(
                  locale,
                  opt.value_ar,
                  opt.value_fa,
                  opt.value_en,
                ) || opt.id.slice(0, 6)}
              </Text>
            </View>
          ))}
        </View>
      ) : null}
      {variant.color_set && variant.color_set.values.length > 0 ? (
        <View style={styles.variantChips}>
          {variant.color_set.values.map((cv) => (
            <View
              key={cv.id}
              style={[
                styles.optionChip,
                {backgroundColor: theme.colors.surfaceVariant},
              ]}>
              <View
                style={colorCircleStyle(cv.color_option?.color_hex ?? null)}
              />
              <Text
                style={[
                  styles.optionChipText,
                  {color: theme.colors.onSurface},
                ]}>
                {cv.piece_name_en ?? ''}:{' '}
                {localeValue(
                  locale,
                  cv.color_option?.value_ar ?? '',
                  cv.color_option?.value_fa ?? '',
                  cv.color_option?.value_en ?? '',
                )}
              </Text>
            </View>
          ))}
        </View>
      ) : null}
      <View style={styles.variantPriceRow}>
        {variant.price != null ? (
          <>
            <Text
              style={[styles.variantPrice, {color: theme.colors.onSurface}]}>
              {formatPrice(variant.price)}
            </Text>
            <Text
              style={[
                styles.variantCurrency,
                {color: theme.colors.onSurfaceVariant},
              ]}>
              {currencyCode}
            </Text>
          </>
        ) : null}
        {variant.original_price != null ? (
          <Text
            style={[
              styles.variantOriginal,
              {color: theme.colors.onSurfaceVariant},
            ]}>
            {formatPrice(variant.original_price)}
          </Text>
        ) : null}
      </View>
      <Text style={[styles.variantQty, {color: theme.colors.onSurfaceVariant}]}>
        Qty: {variant.quantity}
      </Text>
      {variant.barcode ? (
        <Text
          style={[
            styles.variantBarcode,
            {color: theme.colors.onSurfaceVariant},
          ]}>
          Barcode: {variant.barcode}
        </Text>
      ) : null}
    </View>
  );
}

function MetaRow({label, value}: {label: string; value?: string | null}) {
  const theme = useTheme();
  if (!value) {
    return null;
  }
  return (
    <Text style={[styles.metaRow, {color: theme.colors.onSurfaceVariant}]}>
      <Text style={styles.metaLabel}>{label}:</Text> {value}
    </Text>
  );
}

function ProductViewSkeleton() {
  const theme = useTheme();
  const skeletonColor = theme.colors.surfaceVariant;
  return (
    <View style={styles.skeletonContainer}>
      <View style={[styles.skeletonBlock, {backgroundColor: skeletonColor}]} />
      <View style={styles.skeletonLines}>
        {[24, 72, 34, 48, 28, 80].map((width, i) => (
          <View
            key={i}
            style={[
              styles.skeletonLine,
              {width: `${width}%`, backgroundColor: skeletonColor},
            ]}
          />
        ))}
      </View>
    </View>
  );
}

export function ProductViewModal({
  open,
  storeId,
  productId,
  onClose,
}: ProductViewModalProps) {
  const {t} = useTranslation('nav');
  const theme = useTheme();
  const favorite = useFavoriteActions(storeId, productId);

  return (
    <Modal
      visible={open}
      animationType="slide"
      onRequestClose={onClose}
      transparent={false}>
      <SafeAreaView
        style={[styles.modal, {backgroundColor: theme.colors.background}]}>
        <View
          style={[
            styles.modalHeader,
            {
              backgroundColor: theme.colors.surface,
              borderColor: theme.colors.outlineVariant,
            },
          ]}>
          <Text style={[styles.modalTitle, {color: theme.colors.onSurface}]}>
            Product Details
          </Text>
          <View style={styles.modalActions}>
            <IconButton
              icon={favorite.isFavorite ? 'bookmark' : 'bookmark-outline'}
              size={22}
              disabled={favorite.busy || !favorite.enabled}
              onPress={favorite.toggle}
              accessibilityLabel={
                favorite.isFavorite
                  ? t('removeFromFavorites')
                  : t('addToFavorites')
              }
            />
            <IconButton
              icon="close"
              size={20}
              onPress={onClose}
              accessibilityLabel={t('close')}
            />
          </View>
        </View>
        <View style={styles.modalBody}>
          {storeId && productId ? (
            <ProductView storeId={storeId} productId={productId} />
          ) : null}
        </View>
        <View
          style={[
            styles.modalFooter,
            {
              backgroundColor: theme.colors.surface,
              borderColor: theme.colors.outlineVariant,
            },
          ]}>
          <Button
            mode="outlined"
            onPress={onClose}
            style={styles.modalFooterButton}>
            {t('close')}
          </Button>
        </View>
        <FavoriteRemoveDialog
          portal={false}
          visible={favorite.confirmVisible}
          busy={favorite.busy}
          onCancel={favorite.cancelRemove}
          onConfirm={favorite.confirmRemove}
        />
        <SuccessToast usePortal={false} />
        <ErrorToast usePortal={false} />
      </SafeAreaView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  modal: {
    flex: 1,
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderBottomWidth: 1,
  },
  modalTitle: {
    fontSize: 14,
    fontWeight: '600',
  },
  modalActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  modalBody: {
    flex: 1,
  },
  modalFooter: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderTopWidth: 1,
  },
  modalFooterButton: {
    width: '100%',
  },
  productContent: {
    padding: 16,
    gap: 16,
  },
  gallery: {
    gap: 12,
  },
  galleryEmpty: {
    aspectRatio: 1,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: 'transparent',
  },
  mainImage: {
    aspectRatio: 1,
    borderRadius: 12,
    overflow: 'hidden',
  },
  mainImageContent: {
    width: '100%',
    height: '100%',
  },
  colorChips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  colorChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    borderRadius: 999,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  colorChipDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: 'rgba(0,0,0,0.1)',
  },
  colorChipText: {
    fontSize: 12,
    fontWeight: '500',
  },
  thumbnails: {
    gap: 8,
    paddingBottom: 4,
  },
  thumbButton: {
    borderWidth: 2,
    borderRadius: 8,
    overflow: 'hidden',
  },
  thumbImage: {
    width: 64,
    height: 64,
  },
  infoBlock: {
    gap: 8,
  },
  badgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    flexWrap: 'wrap',
  },
  statusBadge: {
    borderRadius: 4,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  statusBadgeText: {
    fontSize: 12,
  },
  createdRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  createdText: {
    fontSize: 12,
  },
  name: {
    fontSize: 24,
    fontWeight: '700',
  },
  nameAr: {
    fontSize: 20,
    fontWeight: '500',
  },
  brand: {
    fontSize: 14,
    fontWeight: '500',
  },
  sourceLink: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  sourceLinkText: {
    fontSize: 14,
    fontWeight: '500',
  },
  priceRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: 8,
  },
  price: {
    fontSize: 30,
    fontWeight: '700',
  },
  currency: {
    fontSize: 14,
  },
  originalPrice: {
    fontSize: 18,
    textDecorationLine: 'line-through',
  },
  discountBadge: {
    borderRadius: 4,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  discountText: {
    fontSize: 12,
    fontWeight: '600',
  },
  priceNotSet: {
    fontSize: 14,
  },
  stock: {
    fontSize: 14,
  },
  description: {
    fontSize: 14,
    lineHeight: 21,
  },
  divider: {
    marginVertical: 4,
  },
  metaRow: {
    fontSize: 14,
  },
  metaLabel: {
    fontWeight: '500',
  },
  section: {
    gap: 8,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
  },
  sectionBody: {
    fontSize: 14,
    lineHeight: 21,
  },
  chipsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  chip: {
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  chipText: {
    fontSize: 14,
  },
  colorSets: {
    gap: 8,
  },
  colorSetCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
    borderRadius: 12,
    padding: 12,
  },
  colorSetValue: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  colorDot: {
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: 'rgba(0,0,0,0.15)',
  },
  colorSetName: {
    fontSize: 12,
  },
  variantsHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
  },
  inactiveToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  inactiveLabel: {
    fontSize: 12,
  },
  variantsGrid: {
    gap: 12,
  },
  variantCard: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 16,
    gap: 6,
  },
  variantInactive: {
    opacity: 0.7,
  },
  variantHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
  },
  variantSku: {
    fontSize: 12,
    fontFamily: 'monospace',
  },
  variantChips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
  },
  optionChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  optionDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: 'rgba(0,0,0,0.1)',
  },
  optionChipText: {
    fontSize: 11,
  },
  variantPriceRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: 6,
  },
  variantPrice: {
    fontSize: 14,
    fontWeight: '700',
  },
  variantCurrency: {
    fontSize: 10,
  },
  variantOriginal: {
    fontSize: 11,
    textDecorationLine: 'line-through',
  },
  variantQty: {
    fontSize: 12,
  },
  variantBarcode: {
    fontSize: 10,
  },
  attrRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: 8,
    paddingVertical: 8,
  },
  attrLabel: {
    fontSize: 12,
    fontWeight: '500',
    textTransform: 'uppercase',
  },
  attrValue: {
    flex: 1,
    fontSize: 14,
  },
  footerMeta: {
    borderTopWidth: 1,
    borderColor: 'transparent',
    paddingTop: 12,
    gap: 2,
  },
  footerText: {
    fontSize: 12,
  },
  notFound: {
    alignItems: 'center',
    gap: 16,
    padding: 48,
    borderRadius: 12,
    borderWidth: 1,
    borderStyle: 'dashed',
    margin: 16,
  },
  notFoundText: {
    fontSize: 14,
  },
  skeletonContainer: {
    gap: 16,
    padding: 16,
  },
  skeletonBlock: {
    aspectRatio: 1,
    borderRadius: 12,
  },
  skeletonLines: {
    gap: 8,
  },
  skeletonLine: {
    height: 16,
    borderRadius: 4,
  },
});
