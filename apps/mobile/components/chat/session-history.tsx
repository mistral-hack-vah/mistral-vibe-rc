import { View, Text, ScrollView } from '@/src/tw';
import type { Message } from './types';
import { TextMessage } from './messages/text-message';
import { ToolCallMessage } from './messages/tool-call-message';
import { AgentNotification } from './messages/agent-notification';

type SessionHistoryProps = {
  messages: Message[];
};

function MessageItem({ message }: { message: Message }) {
  switch (message.type) {
    case 'text':
      return <TextMessage message={message} />;
    case 'tool_call':
      return <ToolCallMessage message={message} />;
    case 'notification':
      return <AgentNotification message={message} />;
  }
}

export function SessionHistory({ messages }: SessionHistoryProps) {
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
    <ScrollView className="flex-1" contentContainerClassName="py-2">
      {messages.map((message, index) => (
        <MessageItem key={index} message={message} />
      ))}
    </ScrollView>
  );
}
