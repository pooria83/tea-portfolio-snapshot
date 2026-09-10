import * as React from 'react';
import {ActivityIndicator, StyleSheet, View} from 'react-native';
import FastImage from '@d11/react-native-fast-image';
import {useTheme} from 'react-native-paper';
import MaterialIcons from 'react-native-vector-icons/MaterialIcons';
import Config from 'react-native-config';
import type {StyleProp} from 'react-native';
import type {ImageStyle as FastImageStyle} from '@d11/react-native-fast-image';

const MAX_ATTEMPTS = 4;
const BACKOFF_MS = [500, 1000, 2000, 4000];
const OPTIMIZER_QUALITY = 75;
const LAST_OPTIMIZER_WIDTH = 3840;

const OPTIMIZER_HOSTS = [
  'https://portfolio.example.invalid/',
  'https://portfolio.example.invalid/',
  'https://portfolio.example.invalid/',
  'https://portfolio.example.invalid/',
] as const;

const OPTIMIZER_WIDTHS = [
  64, 128, 256, 640, 750, 828, 1080, 1200, 1920, 2048, 3840,
] as const;

export function nearestOptimizerWidth(width: number): number {
  return OPTIMIZER_WIDTHS.find((w) => w >= width) ?? LAST_OPTIMIZER_WIDTH;
}

export function isOptimizableSrc(src: string): boolean {
  return OPTIMIZER_HOSTS.some((host) => src.startsWith(host));
}

export function normalizeSrc(src: string, width = 256): string {
  if (!isOptimizableSrc(src)) {
    return src;
  }
  return `${Config.IMAGE_OPTIMIZER_URL}?url=${encodeURIComponent(
    src,
  )}&w=${nearestOptimizerWidth(width)}&q=${OPTIMIZER_QUALITY}`;
}

interface RetryingThumbnailProps {
  src: string;
  alt: string;
  size?: number;
  style?: StyleProp<FastImageStyle>;
  resizeMode?: 'cover' | 'contain';
  optimizedWidth?: number;
}

export function RetryingThumbnail({
  src,
  alt,
  size = 256,
  style,
  resizeMode = 'cover',
  optimizedWidth,
}: RetryingThumbnailProps) {
  const theme = useTheme();
  const [attempt, setAttempt] = React.useState(0);
  const [pending, setPending] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  const [currentSrc, setCurrentSrc] = React.useState(src);

  if (currentSrc !== src) {
    setCurrentSrc(src);
    setAttempt(0);
    setPending(false);
    setLoading(false);
  }

  const optimizedSrc = normalizeSrc(src, optimizedWidth ?? size);
  const canFallback = optimizedSrc !== src;
  const useFallback = canFallback && attempt >= MAX_ATTEMPTS;
  const uri = useFallback ? src : optimizedSrc;
  const failed = canFallback ? attempt > MAX_ATTEMPTS : attempt >= MAX_ATTEMPTS;

  React.useEffect(() => {
    if (!pending) {
      return;
    }
    const isLast = attempt + 1 >= MAX_ATTEMPTS;
    const timer = setTimeout(
      () => {
        setPending(false);
        setAttempt((prev) => prev + 1);
      },
      isLast ? 0 : (BACKOFF_MS[Math.min(attempt, BACKOFF_MS.length - 1)] ?? 0),
    );
    return () => clearTimeout(timer);
  }, [pending, attempt]);

  const handleLoadStart = React.useCallback(() => setLoading(true), []);
  const handleLoadEnd = React.useCallback(() => setLoading(false), []);
  const handleError = React.useCallback(() => {
    setLoading(false);
    setPending(true);
  }, []);

  if (failed) {
    return (
      <View style={[styles.fillCenter, {width: size, height: size}, style]}>
        <MaterialIcons
          name="image"
          size={Math.round(size / 3)}
          color={theme.colors.onSurfaceVariant}
          accessibilityLabel={alt}
        />
      </View>
    );
  }

  if (pending) {
    return (
      <View
        style={[
          styles.fillCenter,
          styles.pending,
          {
            width: size,
            height: size,
            backgroundColor: theme.colors.surfaceVariant,
          },
          style,
        ]}>
        <ActivityIndicator size="small" color={theme.colors.primary} />
      </View>
    );
  }

  return (
    <FastImage
      key={attempt}
      source={{uri}}
      style={[{width: size, height: size}, style]}
      resizeMode={resizeMode}
      accessibilityLabel={alt}
      onLoadStart={handleLoadStart}
      onLoadEnd={handleLoadEnd}
      onError={handleError}>
      {loading ? (
        <View style={styles.spinnerOverlay}>
          <ActivityIndicator size="small" color={theme.colors.primary} />
        </View>
      ) : null}
    </FastImage>
  );
}

const styles = StyleSheet.create({
  fillCenter: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  pending: {
    backgroundColor: 'transparent',
  },
  spinnerOverlay: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
