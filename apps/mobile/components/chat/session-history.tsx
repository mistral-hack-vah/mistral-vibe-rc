import { useRef } from 'react';
import { View, Text } from '@/src/tw';
import { ScrollView as RNScrollView } from 'react-native';
import type { Message } from './types';
import { TextMessage } from './messages/text-message';
import { AgentNotification } from './messages/agent-notification';
import { EditMessage } from './messages/edit-message';

type SessionHistoryProps = {
  messages: Message[];
};

function MistralLogo({ size = 64 }: { size?: number }) {
  // SVG viewBox: 0 0 1271 900 → aspect ratio ~1.41:1
  const aspect = 1271 / 900;
  const width = size * aspect;
  const height = size;
  const sx = width / 1271;
  const sy = height / 900;

  const rect = (x: number, y: number, w: number, h: number, color: string) => (
    <View
      key={`${x}-${y}`}
      style={{
        position: 'absolute',
        left: x * sx,
        top: y * sy,
        width: w * sx,
        height: h * sy,
        backgroundColor: color,
      }}
    />
  );

  return (
    <View style={{ width, height, position: 'relative' }}>
      {/* Top bar */}
      {rect(181, 0, 908, 179, '#FFD800')}
      {rect(181, 179, 908, 180, '#FFAF00')}
      {/* Stem */}
      {rect(363, 359, 544, 181, '#FF8205')}
      {rect(363, 540, 544, 179, '#FA500F')}
      {rect(363, 719, 544, 181, '#E10500')}
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
    case 'notification':
      return <AgentNotification message={message} />;
    case 'status':
      return <StatusIndicator status={message.status} />;
    case 'edit':
      return <EditMessage message={message} />;
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
