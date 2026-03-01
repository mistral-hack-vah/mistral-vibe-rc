import { useEffect, useState } from 'react';
import { KeyboardAvoidingView } from 'react-native';
import { View } from '@/src/tw';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { ChatHeader } from '@/components/chat/chat-header';
import { SessionHistory } from '@/components/chat/session-history';
import { InputModal } from '@/components/chat/input-modal';
import { Sidebar } from '@/components/sidebar';
import { useAgent } from '@/hooks/use-agent';
import type { Attachment } from '@/components/chat/types';

export default function HomeScreen() {
  const insets = useSafeAreaInsets();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const agent = useAgent();

  // Connect on mount
  useEffect(() => {
    agent.connect();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSend = (text: string, attachments: Attachment[]) => {
    agent.sendTextMessage(text, attachments);
  };

  return (
    <View className="flex-1 bg-bg-base" style={{ paddingTop: insets.top }}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior="padding"
        keyboardVerticalOffset={insets.top}
      >
        <ChatHeader
          onSidebarPress={() => setSidebarOpen(true)}
          onSettingsPress={() => {}}
          socketStatus={agent.socketStatus}
          onReconnect={() => agent.connect()}
        />
        <SessionHistory messages={agent.messages} />
        <View style={{ paddingBottom: Math.max(insets.bottom, 8) }}>
          <InputModal
            onSend={handleSend}
            mode={agent.mode}
            onModeChange={agent.setMode}
          />
        </View>
      </KeyboardAvoidingView>

      <Sidebar
        visible={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />
    </View>
  );
}
