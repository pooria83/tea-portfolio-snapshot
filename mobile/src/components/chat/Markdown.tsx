import * as React from 'react';
import {useTheme} from 'react-native-paper';
import MarkdownDisplay from '@ronradtke/react-native-markdown-display';

interface MarkdownProps {
  children: string;
}

function MarkdownComponent({children}: MarkdownProps) {
  const theme = useTheme();
  const onSurface = theme.colors.onSurface;
  const surface = theme.colors.surfaceVariant;
  const border = theme.colors.outlineVariant;

  return (
    <MarkdownDisplay
      style={{
        body: {color: onSurface, fontSize: 14, lineHeight: 21},
        paragraph: {marginBottom: 8},
        heading1: {
          fontSize: 18,
          fontWeight: '600',
          marginBottom: 8,
          color: onSurface,
        },
        heading2: {
          fontSize: 16,
          fontWeight: '600',
          marginBottom: 8,
          color: onSurface,
        },
        heading3: {
          fontSize: 14,
          fontWeight: '600',
          marginBottom: 8,
          color: onSurface,
        },
        bullet_list: {marginBottom: 8},
        ordered_list: {marginBottom: 8},
        list_item: {marginVertical: 2, color: onSurface},
        link: {color: theme.colors.primary, textDecorationLine: 'underline'},
        code_inline: {
          backgroundColor: surface,
          borderRadius: 4,
          paddingHorizontal: 4,
          paddingVertical: 1,
          fontSize: 12,
          color: onSurface,
        },
        strong: {fontWeight: '600', color: onSurface},
        em: {color: onSurface},
        hr: {backgroundColor: border, height: 1, marginVertical: 8},
        table: {marginBottom: 8, borderWidth: 1, borderColor: border},
        thead: {backgroundColor: surface},
        th: {
          borderWidth: 1,
          borderColor: border,
          paddingHorizontal: 8,
          paddingVertical: 6,
        },
        td: {
          borderWidth: 1,
          borderColor: border,
          paddingHorizontal: 8,
          paddingVertical: 6,
        },
        text: {color: onSurface},
        textgroup: {color: onSurface},
      }}>
      {children}
    </MarkdownDisplay>
  );
}

export const Markdown = React.memo(MarkdownComponent);
