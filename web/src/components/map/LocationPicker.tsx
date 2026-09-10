"use client";

import { useEffect, useRef, useMemo } from "react";
import { MapContainer, TileLayer, Marker, useMapEvents, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { LocateControl as LocatePlugin } from "leaflet.locatecontrol";
import "leaflet.locatecontrol/dist/L.Control.Locate.min.css";

delete (L.Icon.Default.prototype as unknown as Record<string, unknown>)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png",
  iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
});

const DEFAULT_CENTER = { lat: 29.3759, lng: 47.9774 };

interface LocationPickerProps {
  value: { lat: number; lng: number } | null;
  onChange: (location: { lat: number; lng: number }) => void;
}

function MapClickHandler({ onChange }: { onChange: (loc: { lat: number; lng: number }) => void }) {
  useMapEvents({
    click(e) {
      onChange({ lat: e.latlng.lat, lng: e.latlng.lng });
    },
  });
  return null;
}

function DraggableMarker({
  position,
  onChange,
}: {
  position: { lat: number; lng: number };
  onChange: (loc: { lat: number; lng: number }) => void;
}) {
  const map = useMap();
  const markerRef = useRef<L.Marker>(null);

  useEffect(() => {
    map.setView([position.lat, position.lng], map.getZoom());
  }, [position, map]);

  const eventHandlers = useMemo(
    () => ({
      dragend() {
        const marker = markerRef.current;
        if (marker) {
          const latlng = marker.getLatLng();
          onChange({ lat: latlng.lat, lng: latlng.lng });
        }
      },
    }),
    [onChange],
  );

  return (
    <Marker
      draggable={true}
      eventHandlers={eventHandlers}
      position={[position.lat, position.lng]}
      ref={markerRef}
    />
  );
}

function LocateControl() {
  const map = useMap();

  useEffect(() => {
    const lc = new LocatePlugin({
      position: "bottomright",
      setView: "untilPan",
      flyTo: true,
      drawCircle: false,
      drawMarker: false,
      showPopup: false,
      strings: { title: "Locate me" },
    });
    map.addControl(lc);
    return () => {
      lc.remove();
    };
  }, [map]);

  return null;
}

export function LocationPicker({ value, onChange }: LocationPickerProps) {
  const center = value
    ? ([value.lat, value.lng] as [number, number])
    : ([DEFAULT_CENTER.lat, DEFAULT_CENTER.lng] as [number, number]);

  return (
    <div className="h-64 w-full overflow-hidden rounded-lg border">
      <MapContainer center={center} zoom={13} className="h-full w-full" scrollWheelZoom={true}>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <MapClickHandler onChange={onChange} />
        <LocateControl />
        {value && <DraggableMarker position={value} onChange={onChange} />}
      </MapContainer>
    </div>
  );
}
