import * as React from 'react';
import {StyleSheet, Text, View} from 'react-native';
import {Button, Icon, useTheme} from 'react-native-paper';

import {Markdown} from './Markdown';
import {CopyButton} from './CopyButton';
import {ProductGrid} from './ProductGrid';
import {intentTheme} from '../../features/chat/intent';
import type {ChatMessage, ChatProduct} from '../../features/chat/types';

interface MessageBubbleProps {
  message: Pick<
    ChatMessage,
    | 'role'
    | 'content'
    | 'product_snapshots'
    | 'debug'
    | 'search_context'
    | 'error'
  >;
  locale?: string | null;
  copyLabel: string;
  copiedLabel: string;
  retryLabel?: string;
  errorText?: string | null;
  onRetry?: () => void;
  onSelectProduct: (product: ChatProduct) => void;
  onFindSimilarProduct?: (product: ChatProduct) => void;
}

export function MessageBubble({
  message,
  locale,
  copyLabel,
  copiedLabel,
  retryLabel,
  errorText,
  onRetry,
  onSelectProduct,
  onFindSimilarProduct,
}: MessageBubbleProps) {
  const theme = useTheme();
  const isUser = message.role === 'user';
  const isErrorTurn =
    !isUser &&
    (message.error != null || message.search_context?.intent === 'error');
  const assistantTheme = intentTheme(
    message.search_context?.intent ?? (message.error ? 'error' : null),
    theme,
  );

  return (
    <View style={[styles.message, isUser && styles.messageEnd]}>
      {!isUser && message.product_snapshots.length > 0 && (
        <ProductGrid
          products={message.product_snapshots}
          {...(locale ? {locale} : {})}
          onSelect={onSelectProduct}
          {...(onFindSimilarProduct
            ? {onFindSimilar: onFindSimilarProduct}
            : {})}
        />
      )}
      <View style={[styles.content, isUser && styles.contentEnd]}>
        <View
          style={[
            styles.bubble,
            isUser
              ? {backgroundColor: theme.colors.primary}
              : {backgroundColor: assistantTheme.backgroundColor},
          ]}>
          {!isUser && assistantTheme.icon ? (
            <View style={styles.bubbleHeader}>
              <Icon
                source={assistantTheme.icon}
                size={14}
                color={theme.colors.onSurfaceVariant}
              />
            </View>
          ) : null}
          {isUser ? (
            <Text style={[styles.userText, {color: theme.colors.onPrimary}]}>
              {message.content}
            </Text>
          ) : isErrorTurn && !message.content ? (
            <Text style={styles.errorText}>{errorText}</Text>
          ) : (
            <Markdown>{message.content}</Markdown>
          )}
        </View>
        {isUser ? (
          <CopyButton
            text={message.content}
            label={copyLabel}
            copiedLabel={copiedLabel}
          />
        ) : null}
        {isErrorTurn && onRetry ? (
          <Button
            mode="outlined"
            compact
            testID="chat-retry"
            onPress={onRetry}
            style={styles.retryButton}
            textColor={theme.colors.error}>
            {retryLabel}
          </Button>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  message: {
    width: '100%',
    gap: 8,
    alignItems: 'flex-start',
  },
  messageEnd: {
    alignItems: 'flex-end',
  },
  content: {
    maxWidth: '80%',
    gap: 6,
  },
  contentEnd: {
    alignItems: 'flex-end',
  },
  bubble: {
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  bubbleHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 2,
  },
  userText: {
    fontSize: 14,
    lineHeight: 21,
  },
  errorText: {
    fontSize: 13,
    lineHeight: 19,
    fontStyle: 'italic',
  },
  retryButton: {
    alignSelf: 'flex-start',
  },
});
