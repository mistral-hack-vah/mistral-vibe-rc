import { View, Text, TextInput, Pressable } from '@/src/tw';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

export default function HomeScreen() {
  const insets = useSafeAreaInsets();

  return (
    <View className="flex-1 bg-bg-base" style={{ paddingTop: insets.top }}>
      {/* Header */}
      <View className="flex-row items-center justify-between px-4 py-3">
        <View className="size-10 rounded-[10px] bg-bg-button items-center justify-center">
          <Text className="text-[13px] font-bold text-text-secondary">VH</Text>
        </View>
        {/*<Pressable className="flex-row items-center gap-1.5 rounded-full bg-bg-button px-3.5 py-1.5">
          <Text className="text-[12px] font-bold text-accent">Get Pro</Text>
          <View className="w-[18px] h-[10px] rounded-[3px] bg-accent" />
        </Pressable>*/}
        <Pressable className="size-10 items-center justify-center">
          <Text className="text-text-secondary text-lg">&#9881;</Text>
        </Pressable>
      </View>

      {/* Center logo area */}
      <View className="flex-1 items-center justify-center">
        <Text className="text-[32px] font-bold text-accent tracking-tight">
          Le Thread
        </Text>
        <Text className="text-sm text-text-secondary mt-1">Vibe on the go</Text>
      </View>

      {/* Chat input bar */}
      <View className="px-4 pb-2" style={{ paddingBottom: Math.max(insets.bottom, 8) }}>
        <View className="flex-row items-center gap-2.5 bg-bg-modal border border-border-soft rounded-2xl px-3.5 py-2.5">
          <Pressable className="size-[30px] rounded-lg bg-bg-button items-center justify-center">
            <Text className="text-text-offwhite text-lg">+</Text>
          </Pressable>
          <TextInput
            className="flex-1 text-[15px] text-text-primary"
            placeholder="Ask Thread"
            placeholderTextColor="#b9b9ba"
          />
          <Pressable className="size-9 rounded-[10px] bg-accent items-center justify-center">
            <Text className="text-white text-sm">&#9650;</Text>
          </Pressable>
        </View>
      </View>
    </View>
  );
}
