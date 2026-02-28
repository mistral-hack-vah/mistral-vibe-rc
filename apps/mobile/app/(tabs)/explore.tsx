import { View, Text, Pressable, ScrollView } from '@/src/tw';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

const SETTINGS_ITEMS = [
  { icon: '&#128451;', label: 'Memories', value: 'Disabled' },
  { icon: '&#9881;', label: 'Instructions', value: 'Default' },
  { icon: '&#127760;', label: 'Connectors' },
  { icon: '&#128218;', label: 'Libraries' },
];

export default function ExploreScreen() {
  const insets = useSafeAreaInsets();

  return (
    <View className="flex-1 bg-bg-void" style={{ paddingTop: insets.top }}>
      {/* Header */}
      <View className="flex-row items-center px-4 py-3.5 border-b border-border-subtle">
        <Text className="flex-1 text-center text-[15px] font-bold text-text-primary">
          Settings
        </Text>
      </View>

      <ScrollView className="flex-1" contentContainerClassName="p-3.5">
        {/* Intelligence section */}
        <View className="bg-bg-surface rounded-card border border-border-subtle mb-5">
          {SETTINGS_ITEMS.map((item, i) => (
            <Pressable
              key={item.label}
              className={`flex-row items-center justify-between px-3.5 py-3 ${
                i < SETTINGS_ITEMS.length - 1 ? 'border-b border-border-subtle' : ''
              }`}>
              <View className="flex-row items-center gap-2.5">
                <View className="size-[30px] rounded-lg bg-brand-orange/15 items-center justify-center">
                  <Text className="text-brand-orange text-sm">{item.icon}</Text>
                </View>
                <Text className="text-[13px] font-medium text-text-primary">{item.label}</Text>
              </View>
              <Text className="text-[12px] text-text-muted">
                {item.value ? `${item.value} ›` : '›'}
              </Text>
            </Pressable>
          ))}
        </View>

        {/* Account section */}
        <Text className="text-[11px] font-semibold tracking-widest uppercase text-text-muted px-1 mb-2.5">
          Account
        </Text>
        <View className="bg-bg-surface rounded-card border border-border-subtle">
          <View className="flex-row items-center justify-between px-3.5 py-3 border-b border-border-subtle">
            <Text className="text-[13px] text-text-secondary">Email</Text>
            <Text className="text-[12px] text-text-muted font-mono">user@email.com</Text>
          </View>
          <View className="flex-row items-center justify-between px-3.5 py-3 border-b border-border-subtle">
            <Text className="text-[13px] text-text-secondary">Subscription</Text>
            <Text className="text-[12px] text-text-muted">Thread Free</Text>
          </View>
          <Pressable className="px-3.5 py-3">
            <Text className="text-[13px] text-brand-orange font-medium">Upgrade now</Text>
          </Pressable>
        </View>

        {/* Pro banner */}
        <View className="mt-5 rounded-card overflow-hidden">
          <View className="bg-brand-orange p-6">
            <Text className="text-lg font-bold text-white mb-1">Le Chat Pro</Text>
            <Text className="text-[26px] font-bold text-white mb-4">
              $19.99<Text className="text-sm font-medium">/mo</Text>
            </Text>
            {['More messages and web searches', 'Extended thinking', 'Deep research reports', 'Up to 15GB storage'].map(
              (feature) => (
                <View key={feature} className="flex-row items-center gap-2 mb-2">
                  <Text className="text-white/90 text-sm">✓</Text>
                  <Text className="text-[13px] text-white/90">{feature}</Text>
                </View>
              )
            )}
            <Pressable className="mt-4 bg-black/25 border border-white/30 rounded-[10px] py-3 items-center">
              <Text className="text-white font-semibold text-sm">Upgrade to Pro</Text>
            </Pressable>
          </View>
        </View>
      </ScrollView>
    </View>
  );
}
