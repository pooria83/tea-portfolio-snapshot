import * as React from 'react';
import {Portal, Snackbar} from 'react-native-paper';

import {useSuccessToastStore} from '../../features/feedback/successToastStore';

interface SuccessToastProps {
  /**
   * Pass `false` when rendered inside a native <Modal>, where Portal content
   * would draw behind the modal window.
   */
  usePortal?: boolean;
}

export default function SuccessToast({usePortal = true}: SuccessToastProps) {
  const message = useSuccessToastStore((state) => state.message);
  const clearMessage = useSuccessToastStore((state) => state.clearMessage);

  const snackbar = (
    <Snackbar
      visible={message != null}
      onDismiss={clearMessage}
      duration={2500}
      accessibilityLiveRegion="polite">
      {message ?? ''}
    </Snackbar>
  );

  return usePortal ? <Portal>{snackbar}</Portal> : snackbar;
}
