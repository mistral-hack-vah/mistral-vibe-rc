import { View, Text, Pressable } from '@/src/tw';
import { ConnectionStatus } from '@/components/connection-status';

const pressStyle = ({ pressed }: { pressed: boolean }) => ({
  opacity: pressed ? 0.85 : 1,
  transform: [{ scale: pressed ? 0.88 : 1 }],
  shadowColor: '#e65d2d',
  shadowOffset: { width: 0, height: 0 },
  shadowOpacity: pressed ? 0.5 : 0,
  shadowRadius: pressed ? 10 : 0,
  elevation: pressed ? 8 : 0,
});

type ChatHeaderProps = {
  onSidebarPress: () => void;
  onSettingsPress: () => void;
};

export function ChatHeader({ onSidebarPress, onSettingsPress }: ChatHeaderProps) {
  return (
    <View className="flex-row items-center justify-between px-4 py-3">
      <Pressable
        onPress={onSidebarPress}
        style={pressStyle}
        className="size-10 rounded-[10px] bg-bg-button items-center justify-center"
      >
        <Text className="text-[13px] font-bold text-text-secondary">VH</Text>
      </Pressable>
      <ConnectionStatus />
      <Pressable
        onPress={onSettingsPress}
        style={pressStyle}
        className="size-10 items-center justify-center"
      >
        <Text className="text-text-secondary text-lg">&#9881;</Text>
      </Pressable>
    </View>
  );
}
