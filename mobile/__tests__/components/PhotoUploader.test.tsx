import {render, waitFor, userEvent} from '@testing-library/react-native';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import MockAdapter from 'axios-mock-adapter';
import * as React from 'react';
import {Alert} from 'react-native';
import {PaperProvider, MD3LightTheme} from 'react-native-paper';
import ImagePicker from 'react-native-image-crop-picker';
import client from '../../src/services/api/client';
import PhotoUploader from '../../src/components/upload/PhotoUploader';

jest.spyOn(Alert, 'alert').mockImplementation(() => undefined);

let mockApi: MockAdapter;

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {retry: false, gcTime: 0},
    mutations: {retry: false, gcTime: 0},
  },
});

const wrapper = ({children}: {children: React.ReactNode}) => (
  <QueryClientProvider client={queryClient}>
    <PaperProvider theme={MD3LightTheme}>{children}</PaperProvider>
  </QueryClientProvider>
);

beforeEach(() => {
  queryClient.clear();
  mockApi = new MockAdapter(client);
});

afterEach(() => {
  queryClient.clear();
  mockApi.restore();
});

describe('PhotoUploader', () => {
  it('picks and crops a photo, uploads it, and reports the url', async () => {
    const user = userEvent.setup();
    const onUploadComplete = jest.fn();
    mockApi.onPost('/files/upload?max_size=400').reply(201, {
      file_name: 'abc.jpg',
      original_name: 'photo.jpg',
      content_type: 'image/jpeg',
      size: 42,
      url: 'https://portfolio.example.invalid/temp-files/abc.jpg',
    });

    const openPicker = ImagePicker.openPicker as jest.Mock;
    openPicker.mockResolvedValue({
      path: 'file:///tmp/photo.jpg',
      mime: 'image/jpeg',
      filename: 'photo.jpg',
    });

    const {getByText} = await render(
      <PhotoUploader currentUrl={null} onUploadComplete={onUploadComplete} />,
      {wrapper},
    );

    await user.press(getByText('changeAvatar'));

    await waitFor(() =>
      expect(onUploadComplete).toHaveBeenCalledWith(
        'https://portfolio.example.invalid/temp-files/abc.jpg',
      ),
    );
    expect(openPicker).toHaveBeenCalledWith(
      expect.objectContaining({cropping: true, mediaType: 'photo'}),
    );
  });

  it('uses a circular crop overlay for avatars', async () => {
    const user = userEvent.setup();
    const openPicker = ImagePicker.openPicker as jest.Mock;
    openPicker.mockResolvedValue({
      path: 'file:///tmp/photo.jpg',
      mime: 'image/jpeg',
      filename: 'photo.jpg',
    });
    mockApi.onPost('/files/upload?max_size=400').reply(201, {
      file_name: 'abc.jpg',
      original_name: 'photo.jpg',
      content_type: 'image/jpeg',
      size: 42,
      url: 'https://portfolio.example.invalid/temp-files/abc.jpg',
    });

    const {getByText} = await render(
      <PhotoUploader currentUrl={null} onUploadComplete={jest.fn()} circular />,
      {wrapper},
    );

    await user.press(getByText('changeAvatar'));

    await waitFor(() => expect(openPicker).toHaveBeenCalled());
    expect(openPicker).toHaveBeenCalledWith(
      expect.objectContaining({cropperCircleOverlay: true}),
    );
  });

  it('ignores user-cancelled selection', async () => {
    const user = userEvent.setup();
    const openPicker = ImagePicker.openPicker as jest.Mock;
    openPicker.mockRejectedValue(new Error('User cancelled image selection'));

    const {getByText} = await render(
      <PhotoUploader currentUrl={null} onUploadComplete={jest.fn()} />,
      {wrapper},
    );

    await user.press(getByText('changeAvatar'));

    await waitFor(() => expect(openPicker).toHaveBeenCalled());
    expect(Alert.alert).not.toHaveBeenCalled();
  });
});
