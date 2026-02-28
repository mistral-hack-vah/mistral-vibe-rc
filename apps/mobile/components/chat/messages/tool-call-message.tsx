import { useState } from 'react';
import { View, Text, Pressable } from '@/src/tw';
import type { ToolCallMessage as ToolCallMessageType } from '../types';

type ToolCallMessageProps = {
  message: ToolCallMessageType;
};

export function ToolCallMessage({ message }: ToolCallMessageProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <View className="px-4 py-1">
      <Pressable
        onPress={() => setExpanded(!expanded)}
        className="bg-bg-modal rounded-card border border-border-subtle px-3.5 py-2.5"
      >
        <View className="flex-row items-center justify-between">
          <Text className="text-[13px] text-text-secondary">
            Ran <Text className="text-accent font-mono">{message.name}</Text>{' '}
            {message.args}
          </Text>
          <Text className="text-text-secondary text-[10px]">
            {expanded ? '▼' : '▶'}
          </Text>
        </View>
        {expanded && message.result && (
          <View className="mt-2 pt-2 border-t border-border-subtle">
            <Text className="text-[13px] text-text-primary font-mono">
              {message.result}
            </Text>
          </View>
        )}
      </Pressable>
    </View>
  );
}
