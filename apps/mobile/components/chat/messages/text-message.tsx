import { View, Text } from '@/src/tw';
import { Image } from '@/src/tw/image';
import Markdown from 'react-native-markdown-display';
import type { TextMessage as TextMessageType } from '../types';

const codeBlockStyle = {
  backgroundColor: 'rgba(255,255,255,0.06)',
  borderRadius: 6,
  padding: 8,
  marginVertical: 4,
};

const markdownRules = {
  fence: (node: any) => (
    <View key={node.key} style={codeBlockStyle}>
      {node.sourceInfo ? (
        <Text style={{ color: '#6b7280', fontSize: 11, fontFamily: 'monospace' }}>
          {node.sourceInfo}
        </Text>
      ) : null}
      <Text style={{ color: '#d1d5db', fontFamily: 'monospace', fontSize: 12 }}>
        {node.content}
      </Text>
    </View>
  ),
  code_inline: (node: any, _children: any, _parent: any, styles: any) => (
    <Text
      key={node.key}
      style={[styles.code_inline, { fontFamily: 'monospace', backgroundColor: 'rgba(255,255,255,0.06)' }]}
    >
      {node.content}
    </Text>
  ),
};

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
          {isUser ? (
            <Text className="text-[15px] text-text-primary leading-[22px]">
              {message.content}
            </Text>
          ) : (
            <>
              <Markdown
                rules={markdownRules}
                style={{
                  body: { color: '#d1d5db', fontSize: 15, lineHeight: 22 },
                  strong: { color: '#f3f4f6' },
                  em: { color: '#d1d5db' },
                  bullet_list: { marginVertical: 4 },
                  ordered_list: { marginVertical: 4 },
                  code_inline: { color: '#d1d5db', fontSize: 13 },
                }}
              >
                {message.content}
              </Markdown>
              {message.isStreaming && <Text style={{ color: '#e65d2d' }}> &#9646;</Text>}
            </>
          )}
        </View>
      )}
    </View>
  );
}
