import * as React from 'react';
import {Portal, Snackbar} from 'react-native-paper';
import {useTranslation} from 'react-i18next';
import {useErrorToastStore} from '../../features/errors/errorToastStore';
import {toUserMessage} from '../../services/api/errors';

interface ErrorToastProps {
  /**
   * Pass `false` when rendered inside a native <Modal>, where Portal content
   * would draw behind the modal window.
   */
  usePortal?: boolean;
}

export default function ErrorToast({usePortal = true}: ErrorToastProps) {
  const {t} = useTranslation();
  const error = useErrorToastStore((state) => state.error);
  const clearError = useErrorToastStore((state) => state.clearError);

  const snackbar = (
    <Snackbar
      visible={error != null}
      onDismiss={clearError}
      duration={4000}
      accessibilityLiveRegion="polite">
      {error != null ? toUserMessage(error, t) : ''}
    </Snackbar>
  );

  return usePortal ? <Portal>{snackbar}</Portal> : snackbar;
}
