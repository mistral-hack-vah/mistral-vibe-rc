import { View, Text, Pressable } from '@/src/tw';
import { Link } from 'expo-router';

export default function ModalScreen() {
  return (
    <View className="flex-1 bg-bg-base items-center justify-center p-5">
      <Text className="text-[24px] font-bold text-text-primary mb-4">This is a modal</Text>
      <Link href="/" dismissTo>
        <Text className="text-brand-orange font-medium text-base">Go to home screen</Text>
      </Link>
    </View>
  );
}
