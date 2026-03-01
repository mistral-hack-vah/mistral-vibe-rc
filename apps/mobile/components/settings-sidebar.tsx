import { useEffect, useRef, useState } from 'react';
import { Animated, TouchableWithoutFeedback } from 'react-native';
import { View, Text, Pressable, ScrollView, TextInput } from '@/src/tw';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { getServerConfig, setServerConfig } from '@/hooks/config';
import type { SocketStatus } from '@/hooks/reconnecting-socket';

const SIDEBAR_WIDTH = 300;

export type SessionMode =
  | 'default'
  | 'plan'
  | 'accept-edits'
  | 'auto-approve'
  | 'chat';

export type ModelId = 'devstral-2' | 'devstral-small';

const SESSION_MODES: { value: SessionMode; label: string }[] = [
  { value: 'default', label: 'Default' },
  { value: 'plan', label: 'Plan' },
  { value: 'accept-edits', label: 'Accept Edits' },
  { value: 'auto-approve', label: 'Auto Approve' },
  { value: 'chat', label: 'Chat' },
];

const MODELS: { value: ModelId; label: string }[] = [
  { value: 'devstral-2', label: 'devstral-2' },
  { value: 'devstral-small', label: 'devstral-small' },
];

// ---------------------------------------------------------------------------
// Dropdown component
// ---------------------------------------------------------------------------
function Dropdown<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
}) {
  const [open, setOpen] = useState(false);
  const current = options.find((o) => o.value === value);

  return (
    <View className="gap-1.5">
      <Text className="text-[12px] font-semibold text-text-secondary uppercase tracking-wider">
        {label}
      </Text>
      <Pressable
        onPress={() => setOpen((v) => !v)}
        className="flex-row items-center justify-between bg-bg-button rounded-[10px] px-3.5 py-3"
      >
        <Text className="text-[14px] text-text-primary">{current?.label}</Text>
        <IconSymbol
          name={open ? 'chevron.up' : 'chevron.down'}
          size={14}
          color="#b9b9ba"
        />
      </Pressable>
      {open && (
        <View className="bg-bg-button rounded-[10px] overflow-hidden border border-border-soft">
          {options.map((opt) => {
            const selected = opt.value === value;
            return (
              <Pressable
                key={opt.value}
                onPress={() => {
                  onChange(opt.value);
                  setOpen(false);
                }}
                className={`px-3.5 py-2.5 ${selected ? 'bg-accent/15' : ''}`}
              >
                <Text
                  className={`text-[14px] ${selected ? 'text-accent font-semibold' : 'text-text-primary'}`}
                >
                  {opt.label}
                </Text>
              </Pressable>
            );
          })}
        </View>
      )}
    </View>
  );
}

// ---------------------------------------------------------------------------
// Status colors
// ---------------------------------------------------------------------------
const STATUS_META: Record<SocketStatus, { color: string; label: string }> = {
  idle: { color: '#6b7280', label: 'Idle' },
  connected: { color: '#34d399', label: 'Connected' },
  connecting: { color: '#f59e0b', label: 'Connecting...' },
  disconnected: { color: '#ef4444', label: 'Disconnected' },
};

// ---------------------------------------------------------------------------
// Settings sidebar
// ---------------------------------------------------------------------------
type SettingsSidebarProps = {
  visible: boolean;
  onClose: () => void;
  socketStatus: SocketStatus;
  onConnect: () => void;
  sessionMode: SessionMode;
  onSessionModeChange: (mode: SessionMode) => void;
  model: ModelId;
  onModelChange: (model: ModelId) => void;
};

export function SettingsSidebar({
  visible,
  onClose,
  socketStatus,
  onConnect,
  sessionMode,
  onSessionModeChange,
  model,
  onModelChange,
}: SettingsSidebarProps) {
  const insets = useSafeAreaInsets();
  const translateX = useRef(new Animated.Value(SIDEBAR_WIDTH)).current;
  const overlayOpacity = useRef(new Animated.Value(0)).current;

  const [hostname, setHostname] = useState('localhost');
  const [port, setPort] = useState('8000');

  // Sync fields when opening
  useEffect(() => {
    if (visible) {
      const config = getServerConfig();
      setHostname(config.hostname);
      setPort(String(config.port));

      Animated.parallel([
        Animated.timing(translateX, {
          toValue: 0,
          duration: 250,
          useNativeDriver: true,
        }),
        Animated.timing(overlayOpacity, {
          toValue: 1,
          duration: 250,
          useNativeDriver: true,
        }),
      ]).start();
    } else {
      Animated.parallel([
        Animated.timing(translateX, {
          toValue: SIDEBAR_WIDTH,
          duration: 200,
          useNativeDriver: true,
        }),
        Animated.timing(overlayOpacity, {
          toValue: 0,
          duration: 200,
          useNativeDriver: true,
        }),
      ]).start();
    }
  }, [visible]);

  const handleConnect = () => {
    const portNum = parseInt(port, 10) || 8000;
    setServerConfig(hostname.trim() || 'localhost', portNum);
    onConnect();
  };

  const { color: statusColor, label: statusLabel } = STATUS_META[socketStatus];

  return (
    <View
      className="absolute inset-0 z-50"
      style={{ pointerEvents: visible ? 'auto' : 'none' }}
    >
      {/* Overlay */}
      <TouchableWithoutFeedback onPress={onClose}>
        <Animated.View
          style={{
            position: 'absolute',
            inset: 0,
            backgroundColor: 'rgba(0,0,0,0.5)',
            opacity: overlayOpacity,
          }}
        />
      </TouchableWithoutFeedback>

      {/* Drawer — slides in from the right */}
      <Animated.View
        style={{
          position: 'absolute',
          top: 0,
          bottom: 0,
          right: 0,
          width: SIDEBAR_WIDTH,
          backgroundColor: '#111115',
          transform: [{ translateX }],
          paddingTop: insets.top + 8,
          paddingBottom: insets.bottom + 8,
        }}
      >
        <View className="flex-1">
          {/* Header */}
          <View className="flex-row items-center justify-between px-4 pt-2 pb-4">
            <Text className="text-[17px] font-bold text-text-primary">
              Settings
            </Text>
            <Pressable
              onPress={onClose}
              className="size-8 items-center justify-center rounded-full bg-bg-button"
            >
              <IconSymbol name="xmark" size={14} color="#b9b9ba" />
            </Pressable>
          </View>

          <ScrollView className="flex-1" contentContainerClassName="px-4 pb-8">
            {/* ── Server Settings ── */}
            <View className="mb-6">
              <Text className="text-xs font-semibold text-accent uppercase tracking-wider mb-3">
                Server
              </Text>

              <View className="bg-bg-modal rounded-[16px] p-4 gap-4 border border-border-subtle">
                {/* Status pill */}
                <View className="flex-row items-center gap-2">
                  <View
                    className="size-2 rounded-full"
                    style={{ backgroundColor: statusColor }}
                  />
                  <Text className="text-[13px] text-text-secondary">
                    {statusLabel}
                  </Text>
                </View>

                {/* Hostname */}
                <View className="gap-1.5">
                  <Text className="text-[12px] font-semibold text-text-secondary uppercase tracking-wider">
                    Hostname
                  </Text>
                  <TextInput
                    className="bg-bg-button rounded-[10px] px-3.5 py-3 text-[14px] text-text-primary"
                    value={hostname}
                    onChangeText={setHostname}
                    placeholder="localhost"
                    placeholderTextColor="#6b7280"
                    autoCapitalize="none"
                    autoCorrect={false}
                    keyboardType="url"
                  />
                </View>

                {/* Port */}
                <View className="gap-1.5">
                  <Text className="text-[12px] font-semibold text-text-secondary uppercase tracking-wider">
                    Port
                  </Text>
                  <TextInput
                    className="bg-bg-button rounded-[10px] px-3.5 py-3 text-[14px] text-text-primary"
                    value={port}
                    onChangeText={setPort}
                    placeholder="8000"
                    placeholderTextColor="#6b7280"
                    keyboardType="number-pad"
                  />
                </View>

                {/* Connect button */}
                <Pressable
                  onPress={handleConnect}
                  className="items-center rounded-[12px] py-3"
                  style={{ backgroundColor: '#e65d2d' }}
                >
                  <Text className="text-[14px] font-bold text-white">
                    Connect
                  </Text>
                </Pressable>
              </View>
            </View>

            {/* ── Vibe Settings ── */}
            <View>
              <Text className="text-xs font-semibold text-accent uppercase tracking-wider mb-3">
                Vibe
              </Text>

              <View className="bg-bg-modal rounded-[16px] p-4 gap-4 border border-border-subtle">
                <Dropdown
                  label="Session Mode"
                  value={sessionMode}
                  options={SESSION_MODES}
                  onChange={onSessionModeChange}
                />

                <Dropdown
                  label="Model"
                  value={model}
                  options={MODELS}
                  onChange={onModelChange}
                />
              </View>
            </View>
          </ScrollView>
        </View>
      </Animated.View>
    </View>
  );
}
