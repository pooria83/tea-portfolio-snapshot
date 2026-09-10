import * as React from 'react';
import {useCallback, useState} from 'react';
import {Pressable, StyleSheet, View} from 'react-native';
import ImagePicker from 'react-native-image-crop-picker';
import {isAxiosError} from 'axios';
import {ActivityIndicator, Text, useTheme} from 'react-native-paper';
import {useTranslation} from 'react-i18next';
import Avatar from '../avatar/Avatar';
import {useUploadFileMutation} from '../../features/profile/useProfileMutations';
import {useErrorToastStore} from '../../features/errors/errorToastStore';
import {classifyError} from '../../services/api/errors';
import {log} from '../../services/logging/logger';

interface PhotoUploaderProps {
  currentUrl: string | null;
  onUploadComplete: (url: string) => void;
  label?: string;
  circular?: boolean;
}

const pickImage = async (circular: boolean) => {
  const image = await ImagePicker.openPicker({
    width: 800,
    height: 800,
    cropping: true,
    cropperCircleOverlay: circular,
    mediaType: 'photo',
    compressImageQuality: 0.9,
  });
  return {
    uri: image.path,
    name: image.filename ?? `photo-${Date.now()}.jpg`,
    type: image.mime ?? 'image/jpeg',
  };
};

export default function PhotoUploader({
  currentUrl,
  onUploadComplete,
  label,
  circular = false,
}: PhotoUploaderProps) {
  const {t} = useTranslation('profile');
  const theme = useTheme();
  const [uploading, setUploading] = useState(false);
  const uploadFile = useUploadFileMutation();
  const showError = useErrorToastStore((state) => state.showError);

  const handlePress = useCallback(async () => {
    try {
      setUploading(true);
      const file = await pickImage(circular);
      const {url} = await uploadFile.mutateAsync(file);
      onUploadComplete(url);
    } catch (error) {
      if (
        error instanceof Error &&
        error.message === 'User cancelled image selection'
      ) {
        return;
      }
      if (!isAxiosError(error)) {
        log.warn('avatar upload flow error', classifyError(error));
      }
      showError(error);
    } finally {
      setUploading(false);
    }
  }, [circular, onUploadComplete, showError, uploadFile]);

  return (
    <View style={styles.container}>
      <Pressable
        onPress={() => {
          void handlePress();
        }}
        accessibilityRole="button"
        disabled={uploading}>
        <View>
          <Avatar url={currentUrl} />
          {uploading && (
            <View
              style={[
                styles.overlay,
                {backgroundColor: theme.colors.backdrop},
              ]}>
              <ActivityIndicator color={theme.colors.onPrimary} />
            </View>
          )}
        </View>
      </Pressable>
      <Pressable
        onPress={() => {
          void handlePress();
        }}
        accessibilityRole="button"
        disabled={uploading}>
        <Text
          variant="labelLarge"
          style={[styles.label, {color: theme.colors.primary}]}>
          {label ?? t('changeAvatar')}
        </Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    gap: 8,
  },
  overlay: {
    ...StyleSheet.absoluteFill,
    borderRadius: 48,
    alignItems: 'center',
    justifyContent: 'center',
    opacity: 0.6,
  },
  label: {
    textDecorationLine: 'underline',
  },
});
