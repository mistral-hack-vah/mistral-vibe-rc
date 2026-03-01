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

function MistralLogo({ size = 64 }: { size?: number }) {
  const unit = size / 16;
  const px = (x: number, y: number, w: number, h: number, color: string) => (
    <View
      key={`${x}-${y}`}
      style={{
        position: 'absolute',
        left: x * unit,
        top: y * unit,
        width: w * unit,
        height: h * unit,
        backgroundColor: color,
      }}
    />
  );

  return (
    <View style={{ width: size, height: size, position: 'relative' }}>
      {/* Battlements */}
      {px(1, 4, 2, 2, '#F5A623')}
      {px(5, 4, 2, 2, '#F5A623')}
      {px(9, 4, 2, 2, '#F5A623')}
      {px(13, 4, 2, 2, '#F5A623')}
      {/* Wall */}
      {px(1, 6, 14, 7, '#F5631A')}
      {/* Gate */}
      {px(6, 9, 4, 4, '#CC3300')}
      {/* Base */}
      {px(3, 13, 10, 2, '#CC3300')}
    </View>
  );
}

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
        <MistralLogo size={96} />
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
