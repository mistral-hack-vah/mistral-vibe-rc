import { View, Text } from '@/src/tw';
import type { TextMessage as TextMessageType } from '../types';

type TextMessageProps = {
  message: TextMessageType;
};

export function TextMessage({ message }: TextMessageProps) {
  const isUser = message.role === 'user';

  return (
    <View className={`px-4 py-1 ${isUser ? 'items-end' : 'items-start'}`}>
      {message.attachments && message.attachments.length > 0 && (
        <View className="flex-row gap-1.5 mb-1">
          {message.attachments.map((attachment, i) => (
            <View key={i} className="bg-bg-button rounded-chip px-2.5 py-1">
              <Text className="text-[11px] text-text-secondary">{attachment}</Text>
            </View>
          ))}
        </View>
      )}
      <View
        className={
          isUser
            ? 'bg-bg-button rounded-card rounded-tr-badge px-3.5 py-2.5 max-w-[85%]'
            : 'max-w-[85%] py-1'
        }
      >
        <Text className="text-[15px] text-text-primary">{message.content}</Text>
      </View>
    </View>
  );
}
