import { View, Text, Pressable } from '@/src/tw';

type ModeSelectorProps = {
  mode: 'plan' | 'build';
  onModeChange: (mode: 'plan' | 'build') => void;
};

export function ModeSelector({ mode, onModeChange }: ModeSelectorProps) {
  return (
    <View className="flex-row items-center gap-0.5 bg-bg-button rounded-chip p-0.5">
      <Pressable
        onPress={() => onModeChange('plan')}
        className={`px-2.5 py-1 rounded-badge ${mode === 'plan' ? 'bg-accent-blue/20' : ''}`}
      >
        <Text
          className={`text-[12px] font-semibold ${mode === 'plan' ? 'text-accent-blue' : 'text-text-secondary'}`}
        >
          Plan
        </Text>
      </Pressable>
      <Pressable
        onPress={() => onModeChange('build')}
        className={`px-2.5 py-1 rounded-badge ${mode === 'build' ? 'bg-accent-blue/20' : ''}`}
      >
        <Text
          className={`text-[12px] font-semibold ${mode === 'build' ? 'text-accent-blue' : 'text-text-secondary'}`}
        >
          Build
        </Text>
      </Pressable>
    </View>
  );
}
