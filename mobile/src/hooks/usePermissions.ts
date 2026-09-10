import * as React from 'react';

import {
  checkLocationPermission,
  checkMicrophonePermission,
  getNotificationsPermission,
  requestLocationPermission,
  requestMicrophonePermission,
  requestNotificationsPermission,
  type NotificationsPermission,
  type PermissionStatus,
} from '../services/permissions/permissions';

export function useNotificationsPermission(): {
  status: NotificationsPermission | null;
  requesting: boolean;
  request: () => Promise<NotificationsPermission>;
} {
  const [status, setStatus] = React.useState<NotificationsPermission | null>(
    null,
  );
  const [requesting, setRequesting] = React.useState(false);

  React.useEffect(() => {
    void getNotificationsPermission().then(setStatus);
  }, []);

  const request = React.useCallback(async () => {
    setRequesting(true);
    try {
      const next = await requestNotificationsPermission();
      setStatus(next);
      return next;
    } finally {
      setRequesting(false);
    }
  }, []);

  return {status, requesting, request};
}

export function useLocationPermission(): {
  status: PermissionStatus | null;
  requesting: boolean;
  request: () => Promise<PermissionStatus>;
  refresh: () => Promise<void>;
} {
  const [status, setStatus] = React.useState<PermissionStatus | null>(null);
  const [requesting, setRequesting] = React.useState(false);

  const refresh = React.useCallback(async () => {
    setStatus(await checkLocationPermission());
  }, []);

  React.useEffect(() => {
    let active = true;
    void checkLocationPermission().then((result) => {
      if (active) {
        setStatus(result);
      }
    });
    return () => {
      active = false;
    };
  }, []);

  const request = React.useCallback(async () => {
    setRequesting(true);
    try {
      const next = await requestLocationPermission();
      setStatus(next);
      return next;
    } finally {
      setRequesting(false);
    }
  }, []);

  return {status, requesting, request, refresh};
}

export function useMicrophonePermission(): {
  status: PermissionStatus | null;
  requesting: boolean;
  request: () => Promise<PermissionStatus>;
} {
  const [status, setStatus] = React.useState<PermissionStatus | null>(null);
  const [requesting, setRequesting] = React.useState(false);

  React.useEffect(() => {
    let active = true;
    void checkMicrophonePermission().then((result) => {
      if (active) {
        setStatus(result);
      }
    });
    return () => {
      active = false;
    };
  }, []);

  const request = React.useCallback(async () => {
    setRequesting(true);
    try {
      const next = await requestMicrophonePermission();
      setStatus(next);
      return next;
    } finally {
      setRequesting(false);
    }
  }, []);

  return {status, requesting, request};
}
