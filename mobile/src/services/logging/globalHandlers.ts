import {log} from './logger';

let installed = false;

export const installGlobalHandlers = (): void => {
  if (installed) {
    return;
  }
  installed = true;

  const defaultHandler = ErrorUtils.getGlobalHandler();
  ErrorUtils.setGlobalHandler((error: unknown, isFatal) => {
    log.error('unhandled JS error', {error, isFatal: isFatal ?? false});
    defaultHandler(error, isFatal ?? false);
  });

  const globalScope = globalThis as typeof globalThis & {
    addEventListener?: (
      type: string,
      listener: (event: {reason?: unknown}) => void,
    ) => void;
  };
  globalScope.addEventListener?.('unhandledrejection', (event) => {
    log.error('unhandled promise rejection', {error: event.reason});
  });
};
