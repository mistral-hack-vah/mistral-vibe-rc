import { useState } from 'react';
import { KeyboardAvoidingView } from 'react-native';
import { View } from '@/src/tw';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { ChatHeader } from '@/components/chat/chat-header';
import { SessionHistory } from '@/components/chat/session-history';
import { InputModal } from '@/components/chat/input-modal';
import { Sidebar } from '@/components/sidebar';
import type { Message, Attachment } from '@/components/chat/types';
import type { AudioRecording } from '@siteed/expo-audio-studio';

export default function HomeScreen() {
  const insets = useSafeAreaInsets();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);

  const handleSend = (text: string, attachments: Attachment[]) => {
    const userMessage: Message = {
      type: 'text',
      role: 'user',
      content: text,
      attachments: attachments.length > 0 ? attachments : undefined,
    };
    setMessages((prev) => [...prev, userMessage]);
  };

  const handleAudioRecorded = (recording: AudioRecording) => {
    // TODO: transcribe or send audio recording
    console.log('Audio recorded:', recording.fileUri, recording.durationMs);
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
        />
        <SessionHistory messages={messages} />
        <View style={{ paddingBottom: Math.max(insets.bottom, 8) }}>
          <InputModal
            onSend={handleSend}
            onAudioRecorded={handleAudioRecorded}
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
