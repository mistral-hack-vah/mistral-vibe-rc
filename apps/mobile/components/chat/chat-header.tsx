import { View, Text, Pressable } from '@/src/tw';
import { ConnectionStatus } from '@/components/connection-status';

type ChatHeaderProps = {
  onSidebarPress: () => void;
  onSettingsPress: () => void;
};

export function ChatHeader({ onSidebarPress, onSettingsPress }: ChatHeaderProps) {
  return (
    <View className="flex-row items-center justify-between px-4 py-3">
      <Pressable
        onPress={onSidebarPress}
        className="size-10 rounded-[10px] bg-bg-button items-center justify-center"
      >
        <Text className="text-[13px] font-bold text-text-secondary">VH</Text>
      </Pressable>
      <ConnectionStatus />
      <Pressable
        onPress={onSettingsPress}
        className="size-10 items-center justify-center"
      >
        <Text className="text-text-secondary text-lg">&#9881;</Text>
      </Pressable>
    </View>
  );
}
