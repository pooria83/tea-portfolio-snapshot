import type {MD3Theme} from 'react-native-paper';

import type {ChatIntent} from './types';

export interface IntentTheme {
  backgroundColor: string;
  icon: string | null;
}

const GREETING_ICON = 'hand-wave';
const SEARCH_ICON = 'magnify';
const GENERAL_ICON = 'auto-fix';
const ERROR_ICON = 'alert-circle';

export function intentTheme(
  intent: ChatIntent | null | undefined,
  theme: MD3Theme,
): IntentTheme {
  switch (intent) {
    case 'greeting':
      return {
        backgroundColor: theme.colors.primaryContainer,
        icon: GREETING_ICON,
      };
    case 'search':
      return {
        backgroundColor: theme.colors.secondaryContainer,
        icon: SEARCH_ICON,
      };
    case 'general':
      return {backgroundColor: theme.colors.surfaceVariant, icon: GENERAL_ICON};
    case 'error':
      return {
        backgroundColor: theme.colors.errorContainer,
        icon: ERROR_ICON,
      };
    default:
      return {backgroundColor: theme.colors.surfaceVariant, icon: null};
  }
}
