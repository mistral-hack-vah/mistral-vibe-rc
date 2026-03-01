import { useEffect, useState } from 'react';
import { KeyboardAvoidingView } from 'react-native';
import { View } from '@/src/tw';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { ChatHeader } from '@/components/chat/chat-header';
import { SessionHistory } from '@/components/chat/session-history';
import { InputModal } from '@/components/chat/input-modal';
import { Sidebar } from '@/components/sidebar';
import {
  SettingsSidebar,
  type SessionMode,
  type ModelId,
} from '@/components/settings-sidebar';
import { useAgent } from '@/hooks/use-agent';
import { usePermissionContext } from '@/contexts/permission-context';
import { PermissionModal, PermissionBadges } from '@/components/permission-modal';
import type { Attachment } from '@/components/chat/types';

export default function HomeScreen() {
  const insets = useSafeAreaInsets();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sessionMode, setSessionMode] = useState<SessionMode>('default');
  const [model, setModel] = useState<ModelId>('devstral-2');

  const permissions = usePermissionContext();
  const agent = useAgent({ requestPermission: permissions.requestPermission });

  // Connect on mount
  useEffect(() => {
    agent.connect();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  // const audioSocket = useAudioSocket();

  // useEffect(() => {
  //   return audioSocket.subscribeMessages((data) => {
  //     if (typeof data !== 'string') return;
  //     try {
  //       const msg = JSON.parse(data);
  //       if (msg.type === 'text') {
  //         setMessages((prev) => {
  //           const last = prev[prev.length - 1];
  //           if (last?.type === 'text' && last.role === 'assistant') {
  //             return [...prev.slice(0, -1), { ...last, content: last.content + msg.content }];
  //           }
  //           return [...prev, { type: 'text', role: 'assistant', content: msg.content }];
  //         });
  //       }
  //       if (msg.type === 'edit') {
  //         setMessages((prev) => [...prev, { type: 'edit', filePath: msg.filePath, diff: msg.diff }]);
  //       }
  //     } catch {}
  //   });
  // }, []);

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
          onSettingsPress={() => setSettingsOpen(true)}
          socketStatus={agent.socketStatus}
          onReconnect={() => agent.connect()}
        />
        <PermissionBadges
          permissions={permissions.permissions}
          onGrantAll={permissions.grantAll}
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

      <SettingsSidebar
        visible={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        socketStatus={agent.socketStatus}
        onConnect={() => agent.connect()}
        sessionMode={sessionMode}
        onSessionModeChange={setSessionMode}
        model={model}
        onModelChange={setModel}
        permissions={permissions.permissions}
        onGrantPermission={permissions.grantPermission}
        onGrantAll={permissions.grantAll}
        onRevokeAll={permissions.revokeAll}
      />

      <PermissionModal
        request={permissions.pendingRequest}
        onRespond={permissions.respondToRequest}
      />
    </View>
  );
}
