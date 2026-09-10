import {render, userEvent, waitFor} from '@testing-library/react-native';
import * as React from 'react';
import {PaperProvider, MD3LightTheme} from 'react-native-paper';
import {
  Map,
  Marker,
  __cameraEaseTo as easeToMock,
  __cameraMock as cameraMock,
  __cameraZoomTo as zoomToMock,
} from '@maplibre/maplibre-react-native';
import LocationPicker from '../../src/components/map/LocationPicker';
import type {LatLng} from '../../src/components/map/LocationPicker';

const wrapper = ({children}: {children: React.ReactNode}) => (
  <PaperProvider theme={MD3LightTheme}>{children}</PaperProvider>
);

const mapMock = Map as unknown as jest.Mock;
const markerMock = Marker as unknown as jest.Mock;

beforeEach(() => {
  mapMock.mockClear();
  cameraMock.mockClear();
  markerMock.mockClear();
  easeToMock.mockClear();
  zoomToMock.mockClear();
});

describe('LocationPicker', () => {
  it('renders the maplibre map centered on the default location', async () => {
    const {getByTestId} = await render(
      <LocationPicker value={null} onChange={jest.fn()} />,
      {wrapper},
    );
    expect(getByTestId('map')).toBeTruthy();
    expect(cameraMock.mock.calls[0][0]).toMatchObject({
      initialViewState: {center: [47.9774, 29.3759], zoom: 13},
      minZoom: 2,
      maxZoom: 22,
    });
    expect(mapMock.mock.calls[0][0]).toMatchObject({
      doubleTapZoom: false,
      doubleTapHoldZoom: false,
    });
  });

  it('centers the map on the provided value', async () => {
    const location: LatLng = {lat: 29.3, lng: 47.9};
    await render(<LocationPicker value={location} onChange={jest.fn()} />, {
      wrapper,
    });
    expect(cameraMock.mock.calls[0][0]).toMatchObject({
      initialViewState: {center: [47.9, 29.3], zoom: 13},
    });
  });

  it('forwards map presses to onChange', async () => {
    const onChange = jest.fn();
    const {getByTestId} = await render(
      <LocationPicker value={null} onChange={onChange} />,
      {wrapper},
    );
    const map = getByTestId('map');
    map.props.onPress({
      nativeEvent: {lngLat: [47.9, 29.3], point: {x: 1, y: 2}},
    });
    await waitFor(() =>
      expect(onChange).toHaveBeenCalledWith({lat: 29.3, lng: 47.9}),
    );
  });

  it('places the pin without moving the camera on tap', async () => {
    const Stateful = () => {
      const [value, setValue] = React.useState<LatLng | null>(null);
      return <LocationPicker value={value} onChange={setValue} />;
    };
    const {getByTestId} = await render(<Stateful />, {wrapper});
    const map = getByTestId('map');
    map.props.onPress({
      nativeEvent: {lngLat: [47.9, 29.3], point: {x: 1, y: 2}},
    });
    await waitFor(() => expect(markerMock).toHaveBeenCalled());
    expect(markerMock.mock.calls.at(-1)?.[0]).toMatchObject({
      lngLat: [47.9, 29.3],
    });
    expect(easeToMock).not.toHaveBeenCalled();
  });

  it('shows a marker at the provided location', async () => {
    const location: LatLng = {lat: 29.3, lng: 47.9};
    const {getByTestId} = await render(
      <LocationPicker value={location} onChange={jest.fn()} />,
      {wrapper},
    );
    expect(getByTestId('map-marker')).toBeTruthy();
    expect(markerMock.mock.calls[0][0]).toMatchObject({lngLat: [47.9, 29.3]});
  });

  it('hides the marker when no location is set', async () => {
    const {queryByTestId} = await render(
      <LocationPicker value={null} onChange={jest.fn()} />,
      {wrapper},
    );
    expect(queryByTestId('map-marker')).toBeNull();
  });

  it('forwards locate requests to onLocateRequested', async () => {
    const user = userEvent.setup();
    const onLocateRequested = jest.fn();
    const {getByTestId} = await render(
      <LocationPicker
        value={null}
        onChange={jest.fn()}
        onLocateRequested={onLocateRequested}
      />,
      {wrapper},
    );
    await user.press(getByTestId('locate-me'));
    await waitFor(() => expect(onLocateRequested).toHaveBeenCalled());
  });

  it('re-centers the camera when the picker regains focus', async () => {
    const location: LatLng = {lat: 29.3, lng: 47.9};
    const {rerender} = await render(
      <LocationPicker value={location} onChange={jest.fn()} />,
      {wrapper},
    );
    easeToMock.mockClear();
    await rerender(
      <LocationPicker value={location} onChange={jest.fn()} focused={false} />,
    );
    await rerender(
      <LocationPicker value={location} onChange={jest.fn()} focused={true} />,
    );
    await waitFor(() =>
      expect(easeToMock).toHaveBeenCalledWith({center: [47.9, 29.3]}),
    );
  });

  it('re-centers the camera when an external location is set', async () => {
    const location: LatLng = {lat: 29.3, lng: 47.9};
    const {rerender} = await render(
      <LocationPicker value={null} onChange={jest.fn()} />,
      {wrapper},
    );
    await rerender(<LocationPicker value={location} onChange={jest.fn()} />);
    await waitFor(() =>
      expect(easeToMock).toHaveBeenCalledWith({center: [47.9, 29.3]}),
    );
  });

  it('does not re-render the camera when the picker re-renders with stable props', async () => {
    const location: LatLng = {lat: 29.3, lng: 47.9};
    const {rerender} = await render(
      <LocationPicker value={location} onChange={jest.fn()} />,
      {wrapper},
    );
    const rendersAfterMount = cameraMock.mock.calls.length;
    await rerender(
      <LocationPicker value={location} onChange={jest.fn()} focused={false} />,
    );
    await rerender(
      <LocationPicker value={location} onChange={jest.fn()} focused={true} />,
    );
    expect(cameraMock.mock.calls.length).toBe(rendersAfterMount);
  });

  it('zooms in by one step via the + button', async () => {
    const user = userEvent.setup();
    const {getByTestId} = await render(
      <LocationPicker value={null} onChange={jest.fn()} />,
      {wrapper},
    );
    getByTestId('map').props.onRegionDidChange({nativeEvent: {zoom: 11}});
    await user.press(getByTestId('zoom-in'));
    await waitFor(() =>
      expect(zoomToMock).toHaveBeenCalledWith(12, {duration: 250}),
    );
  });

  it('zooms out by one step via the - button', async () => {
    const user = userEvent.setup();
    const {getByTestId} = await render(
      <LocationPicker value={null} onChange={jest.fn()} />,
      {wrapper},
    );
    getByTestId('map').props.onRegionDidChange({nativeEvent: {zoom: 11}});
    await user.press(getByTestId('zoom-out'));
    await waitFor(() =>
      expect(zoomToMock).toHaveBeenCalledWith(10, {duration: 250}),
    );
  });

  it('tracks pinch zoom through region changes for subsequent +/- presses', async () => {
    const user = userEvent.setup();
    const {getByTestId} = await render(
      <LocationPicker value={null} onChange={jest.fn()} />,
      {wrapper},
    );
    getByTestId('map').props.onRegionDidChange({nativeEvent: {zoom: 15.5}});
    await user.press(getByTestId('zoom-in'));
    await waitFor(() =>
      expect(zoomToMock).toHaveBeenCalledWith(16.5, {duration: 250}),
    );
  });
});
