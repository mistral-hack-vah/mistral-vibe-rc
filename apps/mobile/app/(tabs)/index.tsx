import { useState } from 'react';
import { KeyboardAvoidingView, Platform } from 'react-native';
import { View } from '@/src/tw';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { ChatHeader } from '@/components/chat/chat-header';
import { SessionHistory } from '@/components/chat/session-history';
import { InputModal } from '@/components/chat/input-modal';
import { Sidebar } from '@/components/sidebar';

export default function HomeScreen() {
  const insets = useSafeAreaInsets();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <View className="flex-1 bg-bg-base" style={{ paddingTop: insets.top }}>
      <KeyboardAvoidingView
        className="flex-1"
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        keyboardVerticalOffset={0}
      >
        <ChatHeader
          onSidebarPress={() => setSidebarOpen(true)}
          onSettingsPress={() => {}}
        />
        <SessionHistory messages={[]} />
        <View style={{ paddingBottom: Math.max(insets.bottom, 8) }}>
          <InputModal onSend={() => {}} />
        </View>
      </KeyboardAvoidingView>

      <Sidebar
        visible={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />
    </View>
  );
}
