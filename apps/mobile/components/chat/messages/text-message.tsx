import { View, Text } from '@/src/tw';
import { Image } from '@/src/tw/image';
import type { TextMessage as TextMessageType } from '../types';

type TextMessageProps = {
  message: TextMessageType;
};

export function TextMessage({ message }: TextMessageProps) {
  const isUser = message.role === 'user';
  const hasAttachments = message.attachments && message.attachments.length > 0;

  return (
    <View className={`px-4 py-1.5 ${isUser ? 'items-end' : 'items-start'}`}>
      {/* Image attachments */}
      {isUser && hasAttachments && (
        <View className="flex-row flex-wrap gap-1.5 mb-1.5 justify-end max-w-[85%]">
          {message.attachments!.map((attachment, i) => (
            <View
              key={i}
              className="rounded-card overflow-hidden"
              style={{
                width: message.attachments!.length === 1 ? 220 : 140,
                height: message.attachments!.length === 1 ? 160 : 120,
              }}
            >
              <Image
                source={attachment.uri}
                className="w-full h-full object-cover"
              />
            </View>
          ))}
        </View>
      )}

      {/* Text bubble */}
      {(message.content.length > 0 || message.isStreaming) && (
        <View
          className={
            isUser
              ? 'bg-bg-button rounded-card rounded-tr-badge px-4 py-3 max-w-[85%]'
              : 'max-w-[92%] py-1 px-1'
          }
        >
          <Text
            className={
              isUser
                ? 'text-[15px] text-text-primary leading-[22px]'
                : 'text-[15px] text-text-primary leading-[22px]'
            }
          >
            {message.content}
            {message.isStreaming && <Text style={{ color: '#e65d2d' }}> &#9646;</Text>}
          </Text>
        </View>
      )}
    </View>
  );
}
