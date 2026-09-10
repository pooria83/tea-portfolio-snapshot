import * as React from 'react';
import {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {
  ActivityIndicator,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  TextInput,
  View,
} from 'react-native';
import type {
  ListRenderItem,
  NativeScrollEvent,
  NativeSyntheticEvent,
} from 'react-native';
import {
  Button,
  Dialog,
  Icon,
  IconButton,
  Portal,
  Text,
  useTheme,
} from 'react-native-paper';
import {useTranslation} from 'react-i18next';
import {useQueryClient} from '@tanstack/react-query';
import {useSafeAreaInsets} from 'react-native-safe-area-context';

import {ChatDrawer} from '../../components/chat/ChatDrawer';
import {Markdown} from '../../components/chat/Markdown';
import {MessageBubble} from '../../components/chat/MessageBubble';
import {ProductGrid} from '../../components/chat/ProductGrid';
import {ProductViewModal} from '../../components/product/ProductViewModal';
import {isChatErrorCode} from '../../features/chat/chatStream';
import {intentTheme} from '../../features/chat/intent';
import {useErrorToastStore} from '../../features/errors/errorToastStore';
import {localeValue, newIdempotencyKey} from '../../features/chat/locale';
import {
  CHATS_QUERY_KEY,
  useCreateConversationMutation,
  useDeleteConversationMutation,
  useGetConversationMessagesQuery,
  useGetConversationsQuery,
} from '../../features/chat/useChatMutations';
import {useChatWebSocket} from '../../features/chat/useChatWebSocket';
import type {ChatMessage, ChatProduct} from '../../features/chat/types';

const INPUT_MAX_HEIGHT = 96;

interface LastTurn {
  kind: 'message' | 'similar';
  content: string;
  idempotencyKey: string;
  productId?: string;
  productName?: string;
}

export default function HomeScreen() {
  const {t} = useTranslation('chat');
  const {t: tCommon} = useTranslation('common');
  const {t: tError} = useTranslation('error');
  const {i18n} = useTranslation();
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const queryClient = useQueryClient();
  const showError = useErrorToastStore((state) => state.showError);

  const [activeId, setActiveId] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [pendingUser, setPendingUser] = useState<string | null>(null);
  const [lastSavedId, setLastSavedId] = useState<string | null>(null);
  const [selectedProduct, setSelectedProduct] = useState<ChatProduct | null>(
    null,
  );
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [inputHeight, setInputHeight] = useState(0);
  const queuedSendRef = useRef<{
    conversationId: string;
    content: string;
    idempotencyKey: string;
  } | null>(null);
  const lastTurnRef = useRef<LastTurn | null>(null);
  const listRef = useRef<FlatList<ChatMessage> | null>(null);
  const nearBottomRef = useRef(true);

  const {
    data: conversations,
    isLoading: chatsLoading,
    error: chatsError,
    refetch: refetchConversations,
  } = useGetConversationsQuery();
  const createConversation = useCreateConversationMutation();
  const deleteConversation = useDeleteConversationMutation();
  const {
    data: history,
    isLoading: historyLoading,
    error: historyError,
    refetch: refetchHistory,
  } = useGetConversationMessagesQuery(activeId);

  const handleMessageSaved = useCallback(
    (message: ChatMessage, conversationId: string) => {
      setPendingUser(null);
      setLastSavedId(message.id);
      void queryClient.invalidateQueries({queryKey: CHATS_QUERY_KEY});
      void queryClient.invalidateQueries({
        queryKey: ['chats', conversationId, 'messages'],
      });
    },
    [queryClient],
  );

  const {
    status,
    stream,
    sendMessage,
    sendSimilarRequest,
    resetStream,
    retryConnect,
  } = useChatWebSocket({
    conversationId: activeId,
    onMessageSaved: handleMessageSaved,
  });

  const activeConversation = useMemo(
    () =>
      conversations?.find((conversation) => conversation.id === activeId) ??
      null,
    [conversations, activeId],
  );
  const isClosed =
    activeConversation?.status === 'closed' ||
    (activeId != null && status === 'closed');

  useEffect(() => {
    if (status !== 'closed' || activeId == null) {
      return;
    }
    queuedSendRef.current = null;
    void queryClient.invalidateQueries({queryKey: CHATS_QUERY_KEY});
  }, [status, activeId, queryClient]);
  const savedVisible =
    lastSavedId != null &&
    (history?.some((message) => message.id === lastSavedId) ?? false);
  const locale = i18n.language;

  useEffect(() => {
    if (stream?.status === 'completed' && savedVisible) {
      resetStream();
    }
  }, [stream?.status, savedVisible, resetStream]);

  useEffect(() => {
    const queued = queuedSendRef.current;
    if (!queued || queued.conversationId !== activeId || status !== 'open') {
      return;
    }
    queuedSendRef.current = null;
    sendMessage(queued.content, queued.idempotencyKey);
  }, [activeId, status, sendMessage]);

  useEffect(() => {
    if (!nearBottomRef.current) {
      return;
    }
    listRef.current?.scrollToOffset({offset: 0, animated: true});
  }, [stream?.content, stream?.products, pendingUser, history]);

  async function handleNewChat() {
    setQuery('');
    setDrawerOpen(false);
    setPendingUser(null);
    setLastSavedId(null);
    queuedSendRef.current = null;
    try {
      const conversation = await createConversation.mutateAsync({
        locale,
        create_new: true,
      });
      setActiveId(conversation.id);
    } catch (error) {
      showError(error);
    }
  }

  async function handleDelete(conversationId: string) {
    setDeleteTarget(null);
    try {
      await deleteConversation.mutateAsync(conversationId);
      if (conversationId === activeId) {
        setActiveId(null);
        setPendingUser(null);
        setLastSavedId(null);
        queuedSendRef.current = null;
      }
    } catch (error) {
      showError(error);
    }
  }

  async function submitQuery() {
    const content = query.trim();
    if (!content || isClosed) {
      return;
    }
    if (activeId == null) {
      setPendingUser(content);
      setQuery('');
      try {
        const conversation = await createConversation.mutateAsync({
          locale,
          create_new: true,
        });
        setActiveId(conversation.id);
        queuedSendRef.current = {
          conversationId: conversation.id,
          content,
          idempotencyKey: newIdempotencyKey(),
        };
      } catch (error) {
        setPendingUser(null);
        setQuery(content);
        showError(error);
      }
      return;
    }
    if (status !== 'open') {
      return;
    }
    setPendingUser(content);
    setQuery('');
    const idempotencyKey = newIdempotencyKey();
    lastTurnRef.current = {kind: 'message', content, idempotencyKey};
    sendMessage(content, idempotencyKey);
  }

  const handleFindSimilar = useCallback(
    (product: ChatProduct) => {
      if (activeId == null || isClosed || status !== 'open') {
        return;
      }
      setPendingUser(null);
      const productName =
        localeValue(
          locale,
          product.name_ar ?? '',
          product.name_fa ?? '',
          product.name_en ?? '',
        ) ||
        product.name ||
        '';
      const idempotencyKey = newIdempotencyKey();
      lastTurnRef.current = {
        kind: 'similar',
        content: productName,
        idempotencyKey,
        productId: product.id,
        productName,
      };
      sendSimilarRequest(product.id, idempotencyKey, productName);
    },
    [activeId, isClosed, status, locale, sendSimilarRequest],
  );

  const handleRetryLastTurn = useCallback(() => {
    const last = lastTurnRef.current;
    if (!last || isClosed || status !== 'open') {
      return;
    }
    if (last.kind === 'similar') {
      const productId = last.productId ?? '';
      if (!productId) {
        return;
      }
      sendSimilarRequest(productId, newIdempotencyKey(), last.productName);
      return;
    }
    setPendingUser(last.content);
    sendMessage(last.content, last.idempotencyKey);
  }, [isClosed, status, sendMessage, sendSimilarRequest]);

  const handleRetryTurn = useCallback(
    (content: string) => {
      if (!content || isClosed || status !== 'open') {
        return;
      }
      setPendingUser(content);
      sendMessage(content, newIdempotencyKey());
    },
    [isClosed, status, sendMessage],
  );

  const creating = createConversation.isPending;
  const connectionFailed = activeId != null && status === 'failed';
  const sendDisabled =
    !query.trim() ||
    creating ||
    isClosed ||
    (activeId != null && status !== 'open' && !connectionFailed);

  let sendLabel = t('send');
  if (activeId != null && status !== 'open') {
    sendLabel =
      status === 'connecting'
        ? t('connecting')
        : connectionFailed
          ? t('retry')
          : t('reconnecting');
  }

  let streamFailureText = t('thinking');
  if (stream?.status === 'failed') {
    streamFailureText =
      stream.error != null && isChatErrorCode(stream.error)
        ? tError(stream.error)
        : t('error');
  }
  const streamIntent =
    stream?.searchContext?.intent ?? (stream?.error ? 'error' : null);
  const streamTheme = intentTheme(streamIntent, theme);

  const showPlaceholder =
    activeId == null ||
    (!historyLoading &&
      historyError == null &&
      history?.length === 0 &&
      !pendingUser &&
      !stream);
  const showHistoryError = activeId != null && historyError != null;

  const historyData = useMemo(
    () => (history ? [...history].reverse() : []),
    [history],
  );

  const renderItem: ListRenderItem<ChatMessage> = useCallback(
    ({item, index}) => {
      const isErrorTurn =
        item.role === 'assistant' &&
        (item.error != null || item.search_context?.intent === 'error');
      const errorText = isErrorTurn
        ? item.error != null && isChatErrorCode(item.error)
          ? tError(item.error)
          : t('error')
        : null;
      const retryContent =
        item.role === 'assistant' ? historyData[index + 1]?.content : undefined;
      return (
        <MessageBubble
          message={item}
          {...(item.locale ? {locale: item.locale} : {})}
          copyLabel={t('copyMessage')}
          copiedLabel={t('copied')}
          retryLabel={t('retry')}
          {...(errorText ? {errorText} : {})}
          {...(isErrorTurn && retryContent
            ? {
                onRetry: () => {
                  handleRetryTurn(retryContent);
                },
              }
            : {})}
          onSelectProduct={setSelectedProduct}
          onFindSimilarProduct={handleFindSimilar}
        />
      );
    },
    [t, tError, handleFindSimilar, handleRetryTurn, historyData],
  );

  const handleScroll = useCallback(
    (event: NativeSyntheticEvent<NativeScrollEvent>) => {
      nearBottomRef.current = event.nativeEvent.contentOffset.y < 200;
    },
    [],
  );

  return (
    <View
      style={[styles.container, {backgroundColor: theme.colors.background}]}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.flex}>
        <View
          style={[
            styles.header,
            {
              backgroundColor: theme.colors.surface,
              borderBottomColor: theme.colors.outlineVariant,
              paddingTop: 8,
            },
          ]}>
          <IconButton
            icon="menu"
            size={24}
            onPress={() => setDrawerOpen(true)}
            accessibilityLabel={t('openConversations')}
          />
          <View style={styles.headerText}>
            <Text
              style={[styles.headerTitle, {color: theme.colors.onSurface}]}
              numberOfLines={1}>
              {t('title')}
            </Text>
            <Text
              style={[
                styles.headerSubtitle,
                {color: theme.colors.onSurfaceVariant},
              ]}
              numberOfLines={1}>
              {t('description')}
            </Text>
          </View>
          <IconButton
            icon="message-plus-outline"
            size={24}
            onPress={() => {
              void handleNewChat();
            }}
            disabled={creating}
            accessibilityLabel={t('newChat')}
          />
        </View>

        {isClosed ? (
          <View
            style={[
              styles.closedBanner,
              {backgroundColor: theme.colors.surfaceVariant},
            ]}>
            <Text
              style={[
                styles.closedText,
                {color: theme.colors.onSurfaceVariant},
              ]}>
              {t('closedNote')}
            </Text>
          </View>
        ) : null}

        {connectionFailed ? (
          <View
            style={[
              styles.closedBanner,
              styles.bannerRow,
              {backgroundColor: theme.colors.errorContainer},
            ]}>
            <Text
              style={[
                styles.closedText,
                {color: theme.colors.onErrorContainer},
              ]}>
              {t('connectionLost')}
            </Text>
            <Button
              mode="text"
              compact
              testID="connection-retry"
              onPress={retryConnect}
              textColor={theme.colors.onErrorContainer}>
              {t('retry')}
            </Button>
          </View>
        ) : null}

        {historyLoading && !history ? (
          <View style={styles.centerFill}>
            <ActivityIndicator size="small" color={theme.colors.primary} />
          </View>
        ) : null}

        {showPlaceholder ? (
          <View style={styles.centerFill}>
            <Text
              style={[
                styles.placeholder,
                {color: theme.colors.onSurfaceVariant},
              ]}>
              {t('placeholder')}
            </Text>
          </View>
        ) : null}

        {showHistoryError ? (
          <View style={styles.centerFill}>
            <Text
              style={[
                styles.placeholder,
                {color: theme.colors.onSurfaceVariant},
              ]}>
              {t('loadFailed')}
            </Text>
            <Button
              mode="outlined"
              compact
              testID="history-retry"
              onPress={() => {
                void refetchHistory();
              }}
              style={styles.retryButton}>
              {t('retry')}
            </Button>
          </View>
        ) : null}

        {!showPlaceholder ? (
          <FlatList
            ref={listRef}
            data={historyData}
            renderItem={renderItem}
            keyExtractor={(item) => item.id}
            inverted
            windowSize={5}
            initialNumToRender={10}
            maxToRenderPerBatch={6}
            updateCellsBatchingPeriod={50}
            style={styles.flex}
            contentContainerStyle={styles.messagesContent}
            keyboardShouldPersistTaps="handled"
            onScroll={handleScroll}
            scrollEventThrottle={16}
            ListHeaderComponent={
              <View style={styles.bottomItems}>
                {pendingUser ? (
                  <MessageBubble
                    message={{
                      role: 'user',
                      content: pendingUser,
                      product_snapshots: [],
                      debug: null,
                      search_context: null,
                      error: null,
                    }}
                    copyLabel={t('copyMessage')}
                    copiedLabel={t('copied')}
                    onSelectProduct={setSelectedProduct}
                  />
                ) : null}
                {stream && (stream.status !== 'completed' || !savedVisible) ? (
                  <View style={styles.messageRow}>
                    {stream.products.length > 0 ? (
                      <ProductGrid
                        products={stream.products}
                        {...(stream.locale ? {locale: stream.locale} : {})}
                        onSelect={setSelectedProduct}
                        onFindSimilar={handleFindSimilar}
                      />
                    ) : null}
                    <View style={styles.messageContent}>
                      <View
                        style={[
                          styles.bubble,
                          {backgroundColor: streamTheme.backgroundColor},
                        ]}>
                        {streamTheme.icon ? (
                          <View style={styles.bubbleHeader}>
                            <Icon
                              source={streamTheme.icon}
                              size={14}
                              color={theme.colors.onSurfaceVariant}
                            />
                          </View>
                        ) : null}
                        {stream.content ? (
                          <Markdown>{stream.content}</Markdown>
                        ) : (
                          <Text
                            style={[
                              styles.thinkingText,
                              {color: theme.colors.onSurfaceVariant},
                            ]}>
                            {streamFailureText}
                          </Text>
                        )}
                      </View>
                      {stream.status === 'failed' ? (
                        <Button
                          mode="outlined"
                          compact
                          testID="chat-retry-stream"
                          onPress={handleRetryLastTurn}
                          textColor={theme.colors.error}>
                          {t('retry')}
                        </Button>
                      ) : null}
                    </View>
                  </View>
                ) : null}
              </View>
            }
          />
        ) : null}

        <View
          style={[
            styles.inputRow,
            {
              backgroundColor: theme.colors.surface,
              borderTopColor: theme.colors.outlineVariant,
              paddingBottom: Math.max(insets.bottom, 12),
            },
          ]}>
          <TextInput
            value={query}
            onChangeText={setQuery}
            placeholder={t('inputPlaceholder')}
            placeholderTextColor={theme.colors.onSurfaceVariant}
            multiline
            maxLength={4000}
            scrollEnabled={inputHeight >= INPUT_MAX_HEIGHT}
            style={[
              styles.input,
              {
                height: Math.max(inputHeight, 44),
                color: theme.colors.onSurface,
              },
            ]}
            onContentSizeChange={(event) => {
              setInputHeight(
                Math.min(
                  event.nativeEvent.contentSize.height,
                  INPUT_MAX_HEIGHT,
                ),
              );
            }}
          />
          <Button
            mode="contained"
            onPress={() => {
              if (connectionFailed) {
                retryConnect();
                return;
              }
              void submitQuery();
            }}
            disabled={sendDisabled}>
            {sendLabel}
          </Button>
        </View>
      </KeyboardAvoidingView>

      <ChatDrawer
        conversations={conversations}
        loading={chatsLoading}
        error={chatsError != null}
        activeId={activeId}
        open={drawerOpen}
        locale={locale}
        creating={creating}
        onOpenChange={setDrawerOpen}
        onRetry={() => {
          void refetchConversations();
        }}
        onSelect={(id) => {
          setActiveId(id);
          setPendingUser(null);
          setLastSavedId(null);
          queuedSendRef.current = null;
          setDrawerOpen(false);
        }}
        onDelete={(id) => {
          setDrawerOpen(false);
          setDeleteTarget(id);
        }}
        onNewChat={() => {
          void handleNewChat();
        }}
      />

      <ProductViewModal
        open={selectedProduct != null}
        storeId={selectedProduct?.store_id ?? ''}
        productId={selectedProduct?.id ?? ''}
        onClose={() => setSelectedProduct(null)}
      />

      <Portal>
        <Dialog
          visible={deleteTarget != null}
          onDismiss={() => setDeleteTarget(null)}>
          <Dialog.Title>{t('deleteChat')}</Dialog.Title>
          <Dialog.Content>
            <Text variant="bodyMedium">{t('deleteConfirm')}</Text>
          </Dialog.Content>
          <Dialog.Actions>
            <Button onPress={() => setDeleteTarget(null)}>
              {tCommon('cancel')}
            </Button>
            <Button
              testID="delete-conversation-confirm"
              textColor={theme.colors.error}
              onPress={() => {
                if (deleteTarget != null) {
                  void handleDelete(deleteTarget);
                }
              }}>
              {tCommon('delete')}
            </Button>
          </Dialog.Actions>
        </Dialog>
      </Portal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  flex: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 8,
    paddingBottom: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  headerText: {
    flex: 1,
    minWidth: 0,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '600',
  },
  headerSubtitle: {
    fontSize: 12,
    marginTop: 1,
  },
  closedBanner: {
    borderRadius: 8,
    marginHorizontal: 16,
    marginTop: 8,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  closedText: {
    fontSize: 12,
  },
  bannerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
  },
  messagesContent: {
    flexGrow: 1,
    padding: 16,
    gap: 12,
  },
  bottomItems: {
    width: '100%',
    gap: 12,
  },
  centerFill: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 160,
  },
  placeholder: {
    fontSize: 14,
    textAlign: 'center',
  },
  retryButton: {
    marginTop: 8,
  },
  messageRow: {
    width: '100%',
    gap: 8,
    alignItems: 'flex-start',
  },
  messageContent: {
    maxWidth: '80%',
    gap: 6,
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
  thinkingText: {
    fontSize: 13,
    fontStyle: 'italic',
  },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 8,
    paddingHorizontal: 12,
    paddingTop: 8,
    borderTopWidth: StyleSheet.hairlineWidth,
  },
  input: {
    flex: 1,
    fontSize: 14,
    maxHeight: INPUT_MAX_HEIGHT,
  },
});
