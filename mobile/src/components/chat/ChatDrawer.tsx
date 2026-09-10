import * as React from 'react';
import {
  ActivityIndicator,
  Animated,
  FlatList,
  I18nManager,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import {Button, IconButton, useTheme} from 'react-native-paper';
import {useTranslation} from 'react-i18next';
import {useSafeAreaInsets} from 'react-native-safe-area-context';

import {relativeTime} from '../../features/chat/locale';
import type {ConversationItem} from '../../features/chat/types';

const PANEL_WIDTH = 288;

interface ChatDrawerProps {
  conversations: ConversationItem[] | undefined;
  loading: boolean;
  error: boolean;
  activeId: string | null;
  open: boolean;
  locale: string;
  creating: boolean;
  onOpenChange: (open: boolean) => void;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onNewChat: () => void;
  onRetry: () => void;
}

export function ChatDrawer({
  conversations,
  loading,
  error,
  activeId,
  open,
  locale,
  creating,
  onOpenChange,
  onSelect,
  onDelete,
  onNewChat,
  onRetry,
}: ChatDrawerProps) {
  const {t} = useTranslation('chat');
  const {t: tCommon} = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const [translateX] = React.useState(
    () => new Animated.Value(I18nManager.isRTL ? PANEL_WIDTH : -PANEL_WIDTH),
  );

  React.useEffect(() => {
    if (open) {
      Animated.timing(translateX, {
        toValue: 0,
        duration: 220,
        useNativeDriver: true,
      }).start();
    }
  }, [open, translateX]);

  const close = () => {
    Animated.timing(translateX, {
      toValue: I18nManager.isRTL ? PANEL_WIDTH : -PANEL_WIDTH,
      duration: 180,
      useNativeDriver: true,
    }).start(() => onOpenChange(false));
  };

  const renderItem = ({item}: {item: ConversationItem}) => {
    const active = item.id === activeId;
    return (
      <View
        style={[
          styles.row,
          active ? {backgroundColor: theme.colors.surfaceVariant} : undefined,
        ]}>
        <Pressable style={styles.rowMain} onPress={() => onSelect(item.id)}>
          <Text
            style={[styles.rowTitle, {color: theme.colors.onSurface}]}
            numberOfLines={1}>
            {item.title ?? t('newChat')}
          </Text>
          <View style={styles.rowMeta}>
            {item.status === 'closed' ? (
              <View
                style={[
                  styles.closedBadge,
                  {backgroundColor: theme.colors.surfaceVariant},
                ]}>
                <Text
                  style={[
                    styles.closedBadgeText,
                    {color: theme.colors.onSurfaceVariant},
                  ]}>
                  {t('closedBadge')}
                </Text>
              </View>
            ) : null}
            <Text
              style={[
                styles.rowMetaText,
                {color: theme.colors.onSurfaceVariant},
              ]}>
              {relativeTime(item.last_activity_at, locale)}
            </Text>
          </View>
        </Pressable>
        <IconButton
          icon="delete-outline"
          size={18}
          iconColor={theme.colors.onSurfaceVariant}
          accessibilityLabel={t('deleteChat')}
          onPress={() => onDelete(item.id)}
        />
      </View>
    );
  };

  return (
    <Modal
      visible={open}
      transparent
      animationType="none"
      onRequestClose={close}>
      <View style={styles.overlay}>
        <Pressable
          style={styles.backdrop}
          onPress={close}
          accessibilityLabel={tCommon('close')}
        />
        <Animated.View
          style={[
            styles.panel,
            {
              backgroundColor: theme.colors.surface,
              borderColor: theme.colors.outlineVariant,
              transform: [{translateX}],
              paddingTop: insets.top,
              paddingBottom: insets.bottom,
            },
          ]}>
          <View style={styles.header}>
            <Button
              mode="contained"
              icon="message-plus-outline"
              onPress={onNewChat}
              disabled={creating}
              style={styles.newChatButton}
              contentStyle={styles.newChatContent}>
              {t('newChat')}
            </Button>
            <IconButton
              icon="close"
              size={20}
              accessibilityLabel={tCommon('close')}
              onPress={close}
            />
          </View>
          {loading ? (
            <View style={styles.center}>
              <ActivityIndicator
                size="small"
                accessibilityLabel={t('loading')}
              />
            </View>
          ) : error ? (
            <View style={styles.center}>
              <Text
                style={[
                  styles.emptyText,
                  {color: theme.colors.onSurfaceVariant},
                ]}>
                {t('loadFailed')}
              </Text>
              <Button
                mode="outlined"
                compact
                testID="chats-retry"
                onPress={onRetry}
                style={styles.retryButton}>
                {t('retry')}
              </Button>
            </View>
          ) : (
            <FlatList
              data={conversations}
              keyExtractor={(item) => item.id}
              renderItem={renderItem}
              contentContainerStyle={styles.listContent}
              ListEmptyComponent={
                <Text
                  style={[
                    styles.emptyText,
                    {color: theme.colors.onSurfaceVariant},
                  ]}>
                  {t('noConversations')}
                </Text>
              }
            />
          )}
        </Animated.View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    flexDirection: 'row',
  },
  backdrop: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
  },
  panel: {
    width: PANEL_WIDTH,
    maxWidth: '85%',
    borderRightWidth: 1,
    height: '100%',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    padding: 12,
  },
  newChatButton: {
    flex: 1,
  },
  newChatContent: {
    justifyContent: 'center',
  },
  listContent: {
    padding: 8,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 8,
    padding: 8,
  },
  rowMain: {
    flex: 1,
    minWidth: 0,
  },
  rowTitle: {
    fontSize: 14,
    fontWeight: '500',
  },
  rowMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 2,
  },
  closedBadge: {
    borderRadius: 4,
    paddingHorizontal: 4,
  },
  closedBadgeText: {
    fontSize: 11,
  },
  rowMetaText: {
    fontSize: 12,
  },
  center: {
    padding: 16,
    alignItems: 'center',
    gap: 8,
  },
  retryButton: {
    alignSelf: 'center',
  },
  emptyText: {
    textAlign: 'center',
    padding: 16,
    fontSize: 12,
  },
});
