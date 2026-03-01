import { View, Text, Pressable } from '@/src/tw';
import type { SocketStatus } from '@/hooks/reconnecting-socket';

const config: Record<SocketStatus, { color: string; label: string }> = {
  idle: { color: '#6b7280', label: 'Idle' },
  connected: { color: '#34d399', label: 'Connected' },
  connecting: { color: '#f59e0b', label: 'Connecting...' },
  disconnected: { color: '#ef4444', label: 'Disconnected' },
};

type ConnectionStatusProps = {
  status: SocketStatus;
  onReconnect: () => void;
};

export function ConnectionStatus({ status, onReconnect }: ConnectionStatusProps) {
  const { color, label } = config[status];

  return (
    <Pressable onPress={onReconnect}>
      <View className="flex-row items-center gap-1.5 rounded-full bg-bg-button px-3.5 py-1.5">
        <View className="size-2 rounded-full" style={{ backgroundColor: color }} />
        <Text className="text-[12px] font-bold text-text-secondary">{label}</Text>
      </View>
    </Pressable>
  );
}
