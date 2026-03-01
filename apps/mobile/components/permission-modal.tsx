/**
 * PermissionModal — Shows permission requests to the user.
 */

import { Modal, Pressable } from 'react-native';
import { View, Text } from '@/src/tw';
import { IconSymbol } from '@/components/ui/icon-symbol';
import type { PermissionRequest, PermissionType, PermissionState } from '@/hooks/use-permissions';

const PERMISSION_INFO: Record<PermissionType, { icon: string; label: string; color: string }> = {
  read: { icon: 'book', label: 'Read Files', color: 'text-accent-blue' },
  edit: { icon: 'pencil', label: 'Edit Files', color: 'text-accent-secondary' },
  execute: { icon: 'play', label: 'Run Commands', color: 'text-accent' },
};

type PermissionModalProps = {
  request: PermissionRequest | null;
  onRespond: (granted: boolean, grantForSession?: boolean) => void;
};

export function PermissionModal({ request, onRespond }: PermissionModalProps) {
  if (!request) return null;

  const info = PERMISSION_INFO[request.type];

  return (
    <Modal visible transparent animationType="fade">
      <View className="flex-1 bg-black/60 justify-center items-center px-6">
        <View className="bg-bg-modal rounded-2xl w-full max-w-sm p-5 border border-border-subtle">
          {/* Header */}
          <View className="items-center mb-4">
            <View className="w-16 h-16 rounded-full bg-bg-button items-center justify-center mb-3">
              <IconSymbol name={info.icon as any} size={32} color={info.color.split('-')[1] || 'white'} />
            </View>
            <Text className={`text-xl font-semibold ${info.color}`}>
              {info.label} Permission
            </Text>
          </View>

          {/* Description */}
          <Text className="text-text-primary text-center text-base mb-2">
            {request.description}
          </Text>

          {request.detail && (
            <View className="bg-bg-base rounded-lg p-3 mb-4">
              <Text className="text-text-secondary font-mono text-sm" numberOfLines={3}>
                {request.detail}
              </Text>
            </View>
          )}

          {/* Actions */}
          <View className="gap-3 mt-4">
            {/* Allow for session */}
            <Pressable
              onPress={() => onRespond(true, true)}
              className="bg-accent py-4 rounded-2xl active:opacity-90"
            >
              <Text className="text-white text-center font-semibold text-base">
                Allow Always
              </Text>
            </Pressable>

            {/* Allow once */}
            <Pressable
              onPress={() => onRespond(true, false)}
              className="bg-bg-button py-4 rounded-2xl border border-border-subtle active:opacity-90"
            >
              <Text className="text-text-primary text-center font-medium text-base">
                Allow Once
              </Text>
            </Pressable>

            {/* Deny */}
            <Pressable
              onPress={() => onRespond(false)}
              className="py-3 active:opacity-80"
            >
              <Text className="text-text-secondary text-center text-base">
                Deny
              </Text>
            </Pressable>
          </View>
        </View>
      </View>
    </Modal>
  );
}

type PermissionBadgesProps = {
  permissions: PermissionState;
  onGrantAll: () => void;
};

export function PermissionBadges({ permissions, onGrantAll }: PermissionBadgesProps) {
  const allGranted = permissions.read && permissions.edit && permissions.execute;

  if (allGranted) return null;

  return (
    <View className="flex-row items-center gap-3 px-4 py-3 bg-bg-modal border-b border-border-subtle">
      <Text className="text-text-secondary text-sm font-medium">Permissions:</Text>

      <View className="flex-row gap-2 flex-1">
        {Object.entries(PERMISSION_INFO).map(([type, info]) => (
          <View
            key={type}
            className={`px-3 py-1 rounded-full flex-row items-center gap-1 ${
              permissions[type as PermissionType]
                ? 'bg-accent/10 border border-accent/20'
                : 'bg-gray-500/20 border border-border-subtle'
            }`}
          >
            <IconSymbol name={info.icon as any} size={14} color={permissions[type as PermissionType] ? 'white' : 'gray'} />
            <Text className={`text-xs ${permissions[type as PermissionType] ? 'text-accent' : 'text-text-secondary'}`}>
              {permissions[type as PermissionType] ? '✓' : '○'}
            </Text>
          </View>
        ))}
      </View>

      <Pressable
        onPress={onGrantAll}
        className="bg-accent/20 px-4 py-2 rounded-full active:opacity-80"
      >
        <Text className="text-accent text-sm font-medium">Allow All</Text>
      </Pressable>
    </View>
  );
}
