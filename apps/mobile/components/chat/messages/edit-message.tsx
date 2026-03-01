import { useState } from 'react';
import { Pressable, Text, View } from '@/src/tw';
import { ScrollView } from 'react-native';
import type { ToolCallMessage } from '../types';

type EditMessageProps = {
  message: ToolCallMessage;
};

function DiffView({ diff }: { diff: string }) {
  const lines = diff.split('\n');
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false}>
      <View>
        {lines.map((line, i) => {
          const isAdd = line.startsWith('+') && !line.startsWith('+++');
          const isDel = line.startsWith('-') && !line.startsWith('---');
          const isHunk = line.startsWith('@@');
          const isMeta = line.startsWith('+++') || line.startsWith('---');
          if (isMeta) return null;
          return (
            <View
              key={i}
              style={{
                backgroundColor: isAdd
                  ? 'rgba(52,211,153,0.12)'
                  : isDel
                    ? 'rgba(248,113,113,0.12)'
                    : isHunk
                      ? 'rgba(255,255,255,0.04)'
                      : 'transparent',
                paddingHorizontal: 8,
                paddingVertical: 1,
              }}
            >
              <Text
                style={{
                  fontFamily: 'monospace',
                  fontSize: 12,
                  color: isAdd ? '#34d399' : isDel ? '#f87171' : isHunk ? '#6b7280' : '#d1d5db',
                }}
              >
                {line}
              </Text>
            </View>
          );
        })}
      </View>
    </ScrollView>
  );
}

export function EditMessage({ message }: EditMessageProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <View className="px-4 py-1">
      <Pressable
        onPress={() => setExpanded(!expanded)}
        className="bg-bg-modal rounded-card border border-border-subtle px-3.5 py-2.5"
      >
        <View className="flex-row items-center justify-between">
          <Text className="text-[13px] text-text-secondary">
            Edit <Text className="text-text-primary font-mono">{message.filePath}</Text>
          </Text>
          <Text className="text-text-secondary text-[10px]">{expanded ? '▼' : '▶'}</Text>
        </View>

        {expanded && (
          <View className="mt-2 pt-2 border-t border-border-subtle">
            <DiffView diff={message.diff} />
          </View>
        )}
      </Pressable>
    </View>
  );
}
