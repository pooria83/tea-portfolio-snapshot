import * as React from 'react';
import {Pressable, StyleSheet, Text} from 'react-native';
import {useTheme} from 'react-native-paper';
import Clipboard from '@react-native-clipboard/clipboard';
import MaterialIcons from 'react-native-vector-icons/MaterialIcons';

import {log} from '../../services/logging/logger';

interface CopyButtonProps {
  text: string;
  label: string;
  copiedLabel: string;
}

export function CopyButton({text, label, copiedLabel}: CopyButtonProps) {
  const theme = useTheme();
  const [copied, setCopied] = React.useState(false);

  const handleCopy = () => {
    Clipboard.setString(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
    log.debug('copy_message', {length: text.length});
  };

  return (
    <Pressable
      onPress={handleCopy}
      accessibilityRole="button"
      accessibilityLabel={copied ? copiedLabel : label}
      style={styles.button}>
      <MaterialIcons
        name={copied ? 'check' : 'content-copy'}
        size={14}
        color={theme.colors.onSurfaceVariant}
      />
      {copied ? (
        <Text style={[styles.label, {color: theme.colors.onSurfaceVariant}]}>
          {copiedLabel}
        </Text>
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    alignSelf: 'flex-start',
  },
  label: {
    fontSize: 12,
  },
});
