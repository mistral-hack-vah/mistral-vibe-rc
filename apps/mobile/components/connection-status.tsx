import { View, Text } from '@/src/tw';
import { useWebSocket, type ConnectionStatus as Status } from '@/hooks/use-websocket';

const config: Record<Status, { color: string; label: string }> = {
  connected: { color: '#34d399', label: 'Connected' },
  connecting: { color: '#f59e0b', label: 'Connecting...' },
  disconnected: { color: '#ef4444', label: 'Disconnected' },
};

export function ConnectionStatus() {
  const status = useWebSocket();
  const { color, label } = config[status];

  return (
    <View className="flex-row items-center gap-1.5 rounded-full bg-bg-button px-3.5 py-1.5">
      <View className="size-2 rounded-full" style={{ backgroundColor: color }} />
      <Text className="text-[12px] font-bold text-text-secondary">{label}</Text>
    </View>
  );
}
