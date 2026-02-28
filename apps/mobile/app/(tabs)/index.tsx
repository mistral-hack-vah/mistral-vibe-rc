import { View } from '@/src/tw';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { ChatHeader } from '@/components/chat/chat-header';
import { SessionHistory } from '@/components/chat/session-history';
import { InputModal } from '@/components/chat/input-modal';

export default function HomeScreen() {
  const insets = useSafeAreaInsets();

  return (
    <View className="flex-1 bg-bg-base" style={{ paddingTop: insets.top }}>
      <ChatHeader onSidebarPress={() => {}} onSettingsPress={() => {}} />
      <SessionHistory messages={[]} />
      <View style={{ paddingBottom: Math.max(insets.bottom, 8) }}>
        <InputModal onSend={() => {}} />
      </View>
    </View>
  );
}
