/**
 * PermissionModal — Shows permission requests to the user.
 */

import { Modal, Pressable } from 'react-native';
import { View, Text } from '@/src/tw';
import type { PermissionRequest, PermissionType, PermissionState } from '@/hooks/use-permissions';

const PERMISSION_INFO: Record<PermissionType, { icon: string; label: string; color: string }> = {
  read: { icon: '📄', label: 'Read Files', color: 'text-blue-400' },
  edit: { icon: '✏️', label: 'Edit Files', color: 'text-yellow-400' },
  execute: { icon: '⚡', label: 'Run Commands', color: 'text-red-400' },
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
            <Text className="text-4xl mb-2">{info.icon}</Text>
            <Text className={`text-lg font-semibold ${info.color}`}>
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
          <View className="gap-2 mt-2">
            {/* Allow for session */}
            <Pressable
              onPress={() => onRespond(true, true)}
              className="bg-accent py-3 rounded-xl active:opacity-80"
            >
              <Text className="text-white text-center font-semibold">
                Allow Always
              </Text>
            </Pressable>

            {/* Allow once */}
            <Pressable
              onPress={() => onRespond(true, false)}
              className="bg-bg-base py-3 rounded-xl border border-border-subtle active:opacity-80"
            >
              <Text className="text-text-primary text-center font-medium">
                Allow Once
              </Text>
            </Pressable>

            {/* Deny */}
            <Pressable
              onPress={() => onRespond(false)}
              className="py-3 active:opacity-80"
            >
              <Text className="text-text-secondary text-center">
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
    <View className="flex-row items-center gap-2 px-4 py-2 bg-bg-modal border-b border-border-subtle">
      <Text className="text-text-secondary text-xs">Permissions:</Text>

      {Object.entries(PERMISSION_INFO).map(([type, info]) => (
        <View
          key={type}
          className={`px-2 py-1 rounded-full ${
            permissions[type as PermissionType]
              ? 'bg-green-500/20'
              : 'bg-gray-500/20'
          }`}
        >
          <Text className="text-xs">
            {info.icon} {permissions[type as PermissionType] ? '✓' : '○'}
          </Text>
        </View>
      ))}

      <Pressable
        onPress={onGrantAll}
        className="ml-auto bg-accent/20 px-3 py-1 rounded-full active:opacity-80"
      >
        <Text className="text-accent text-xs font-medium">Allow All</Text>
      </Pressable>
    </View>
  );
}
