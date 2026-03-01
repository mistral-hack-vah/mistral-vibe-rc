import { useRef } from 'react';
import { View, Text } from '@/src/tw';
import { ScrollView as RNScrollView } from 'react-native';
import type { Message } from './types';
import { TextMessage } from './messages/text-message';
import { ToolCallMessage } from './messages/tool-call-message';
import { AgentNotification } from './messages/agent-notification';

type SessionHistoryProps = {
  messages: Message[];
};

function StatusIndicator({ status }: { status: 'recording' | 'transcribing' }) {
  const label = status === 'recording' ? 'Recording...' : 'Transcribing...';
  const color = status === 'recording' ? '#ef4444' : '#f59e0b';

  return (
    <View className="py-2 items-center flex-row justify-center gap-2">
      <View className="size-2 rounded-full" style={{ backgroundColor: color }} />
      <Text className="text-text-secondary text-[12px]">{label}</Text>
    </View>
  );
}

function MessageItem({ message }: { message: Message }) {
  switch (message.type) {
    case 'text':
      return <TextMessage message={message} />;
    case 'tool_call':
      return <ToolCallMessage message={message} />;
    case 'notification':
      return <AgentNotification message={message} />;
    case 'status':
      return <StatusIndicator status={message.status} />;
  }
}

export function SessionHistory({ messages }: SessionHistoryProps) {
  const scrollRef = useRef<RNScrollView>(null);

  if (messages.length === 0) {
    return (
      <View className="flex-1 items-center justify-center">
        <Text className="text-[32px] font-bold text-accent tracking-tight">
          Le Thread
        </Text>
        <Text className="text-sm text-text-secondary mt-1">Vibe on the go</Text>
      </View>
    );
  }

  return (
    <RNScrollView
      ref={scrollRef}
      style={{ flex: 1 }}
      contentContainerStyle={{ paddingVertical: 12 }}
      onContentSizeChange={() => {
        scrollRef.current?.scrollToEnd({ animated: true });
      }}
    >
      {messages.map((message, index) => (
        <MessageItem key={index} message={message} />
      ))}
    </RNScrollView>
  );
}
