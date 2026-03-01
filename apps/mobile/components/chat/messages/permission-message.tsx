/**
 * PermissionMessage — Displays read/edit/execute permission requests in chat.
 */

import { View, Text } from '@/src/tw';
import type { ReadRequestMessage, ExecuteRequestMessage, ToolCallMessage } from '../types';

type PermissionMessageProps = {
  message: ReadRequestMessage | ExecuteRequestMessage | ToolCallMessage;
};

const STATUS_STYLES = {
  pending: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', label: 'Pending' },
  approved: { bg: 'bg-green-500/20', text: 'text-green-400', label: 'Approved' },
  denied: { bg: 'bg-red-500/20', text: 'text-red-400', label: 'Denied' },
};

const TYPE_INFO = {
  read_request: { icon: '📄', label: 'Read File' },
  execute_request: { icon: '⚡', label: 'Run Command' },
  edit: { icon: '✏️', label: 'Edit File' },
};

export function PermissionMessage({ message }: PermissionMessageProps) {
  const status = message.status || 'approved';
  const statusStyle = STATUS_STYLES[status];
  const typeInfo = TYPE_INFO[message.type];

  const detail =
    message.type === 'execute_request'
      ? message.command
      : message.type === 'read_request'
      ? message.filePath
      : message.filePath;

  return (
    <View className="px-4 py-1">
      <View className="bg-bg-modal rounded-card border border-border-subtle px-3.5 py-2.5">
        <View className="flex-row items-center justify-between mb-1">
          <View className="flex-row items-center gap-2">
            <Text className="text-lg">{typeInfo.icon}</Text>
            <Text className="text-[13px] text-text-primary font-medium">
              {typeInfo.label}
            </Text>
          </View>
          <View className={`px-2 py-0.5 rounded-full ${statusStyle.bg}`}>
            <Text className={`text-[10px] font-medium ${statusStyle.text}`}>
              {statusStyle.label}
            </Text>
          </View>
        </View>
        <View className="bg-bg-base rounded-lg p-2 mt-1">
          <Text
            className="text-[12px] text-text-secondary font-mono"
            numberOfLines={2}
          >
            {detail}
          </Text>
        </View>
      </View>
    </View>
  );
}
