import * as React from 'react';
import {Dialog, Button, Portal, Text, useTheme} from 'react-native-paper';
import {useTranslation} from 'react-i18next';

interface FavoriteRemoveDialogProps {
  visible: boolean;
  onCancel: () => void;
  onConfirm: () => void;
  busy?: boolean;
  /**
   * When rendered inside a native <Modal>, Portal content draws behind the
   * modal window, so pass `portal={false}` to render the dialog in place.
   */
  portal?: boolean;
}

export default function FavoriteRemoveDialog({
  visible,
  onCancel,
  onConfirm,
  busy = false,
  portal = true,
}: FavoriteRemoveDialogProps) {
  const {t} = useTranslation('nav');
  const theme = useTheme();

  const dialog = (
    <Dialog visible={visible} onDismiss={onCancel}>
      <Dialog.Title>{t('removeFavoriteTitle')}</Dialog.Title>
      <Dialog.Content>
        <Text variant="bodyMedium">{t('removeFavoriteMessage')}</Text>
      </Dialog.Content>
      <Dialog.Actions>
        <Button onPress={onCancel} disabled={busy}>
          {t('cancel', {ns: 'common'})}
        </Button>
        <Button
          testID="confirm-remove-favorite"
          textColor={theme.colors.error}
          loading={busy}
          onPress={onConfirm}>
          {t('remove')}
        </Button>
      </Dialog.Actions>
    </Dialog>
  );

  return portal ? <Portal>{dialog}</Portal> : dialog;
}
