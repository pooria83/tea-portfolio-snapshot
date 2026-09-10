import * as React from 'react';
import {useEffect, useRef, useState} from 'react';
import {StyleSheet, View} from 'react-native';
import {Camera, Map, Marker} from '@maplibre/maplibre-react-native';
import type {
  CameraRef,
  InitialViewState,
  PressEvent,
  ViewStateChangeEvent,
} from '@maplibre/maplibre-react-native';
import {IconButton, useTheme} from 'react-native-paper';
import {log} from '../../services/logging/logger';

export interface LatLng {
  lat: number;
  lng: number;
}

interface LocationPickerProps {
  value: LatLng | null;
  onChange: (location: LatLng) => void;
  onLocateRequested?: () => void;
  focused?: boolean;
  height?: number;
}

const DEFAULT_CENTER: LatLng = {lat: 29.3759, lng: 47.9774};

const INITIAL_ZOOM = 13;

const MIN_ZOOM = 2;

const MAX_ZOOM = 22;

// Free OSM-based vector style, no API key required.
const MAP_STYLE = 'https://tiles.openfreemap.org/styles/liberty';

export default function LocationPicker({
  value,
  onChange,
  onLocateRequested,
  focused = true,
  height = 256,
}: LocationPickerProps) {
  const theme = useTheme();
  const center = value ?? DEFAULT_CENTER;
  const cameraRef = useRef<CameraRef>(null);
  // Captured once at mount with stable object identity so the lib's memo-ized
  // Camera never re-renders. A re-render would push a fresh empty `stop` prop
  // to native `setStop`, whose moveCamera call cancels any in-flight gesture.
  const [initialViewState] = useState<InitialViewState>(() => ({
    center: [center.lng, center.lat],
    zoom: INITIAL_ZOOM,
  }));
  const zoomRef = useRef(INITIAL_ZOOM);
  // The camera is imperative so user zoom/pan is never reset. A tap places the
  // pin under the finger without moving the map; external changes (locate-me,
  // tab refocus) re-center at the current zoom via easeTo.
  const tappedRef = useRef(false);
  const prevFocusedRef = useRef(focused);

  const handlePress = (event: {nativeEvent: PressEvent}) => {
    const [lng, lat] = event.nativeEvent.lngLat;
    tappedRef.current = true;
    onChange({lat, lng});
  };

  const handleRegionDidChange = (event: {
    nativeEvent: ViewStateChangeEvent;
  }) => {
    zoomRef.current = event.nativeEvent.zoom;
  };

  const zoomBy = (delta: number) => {
    cameraRef.current?.zoomTo(zoomRef.current + delta, {duration: 250});
  };

  useEffect(() => {
    if (tappedRef.current) {
      tappedRef.current = false;
      return;
    }
    if (value) {
      cameraRef.current?.easeTo({center: [value.lng, value.lat]});
    }
  }, [value]);

  useEffect(() => {
    const gainedFocus = focused && !prevFocusedRef.current;
    prevFocusedRef.current = focused;
    if (gainedFocus && value) {
      cameraRef.current?.easeTo({center: [value.lng, value.lat]});
    }
  }, [focused, value]);

  return (
    <View
      style={[styles.container, {height, borderColor: theme.colors.outline}]}>
      <Map
        testID="map"
        style={styles.map}
        mapStyle={MAP_STYLE}
        doubleTapZoom={false}
        doubleTapHoldZoom={false}
        onPress={handlePress}
        onRegionDidChange={handleRegionDidChange}>
        <Camera
          ref={cameraRef}
          initialViewState={initialViewState}
          minZoom={MIN_ZOOM}
          maxZoom={MAX_ZOOM}
        />
        {value != null ? (
          <Marker
            testID="map-marker"
            lngLat={[value.lng, value.lat]}
            anchor="bottom">
            <View pointerEvents="none">
              <IconButton icon="map-marker" size={32} />
            </View>
          </Marker>
        ) : null}
      </Map>
      <IconButton
        testID="locate-me"
        icon="crosshairs-gps"
        size={22}
        mode="contained"
        style={styles.locateButton}
        onPress={() => {
          log.debug('map locate button pressed');
          onLocateRequested?.();
        }}
      />
      <IconButton
        testID="zoom-out"
        icon="minus"
        size={22}
        mode="contained"
        style={styles.zoomOutButton}
        onPress={() => zoomBy(-1)}
      />
      <IconButton
        testID="zoom-in"
        icon="plus"
        size={22}
        mode="contained"
        style={styles.zoomInButton}
        onPress={() => zoomBy(1)}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    overflow: 'hidden',
    borderRadius: 8,
    borderWidth: 1,
  },
  map: {
    flex: 1,
  },
  locateButton: {
    position: 'absolute',
    right: 8,
    bottom: 8,
  },
  zoomOutButton: {
    position: 'absolute',
    right: 8,
    bottom: 56,
  },
  zoomInButton: {
    position: 'absolute',
    right: 8,
    bottom: 104,
  },
});
