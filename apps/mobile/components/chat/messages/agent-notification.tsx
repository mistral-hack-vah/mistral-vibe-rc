import { View, Text } from '@/src/tw';
import type { AgentNotification as AgentNotificationType } from '../types';

type AgentNotificationProps = {
  message: AgentNotificationType;
};

export function AgentNotification({ message }: AgentNotificationProps) {
  return (
    <View className="py-2 items-center">
      <Text className="text-text-secondary text-[12px]">{message.content}</Text>
    </View>
  );
}
