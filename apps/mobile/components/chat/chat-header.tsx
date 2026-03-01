import { View, Text, Pressable } from '@/src/tw';
import { useState } from 'react';
import { ConnectionStatus } from '@/components/connection-status';
import type { SocketStatus } from '@/hooks/reconnecting-socket';
import type { RepoConfig } from '@/hooks/api-client';

const pressStyle = ({ pressed }: { pressed: boolean }) => ({
  opacity: pressed ? 0.85 : 1,
  transform: [{ scale: pressed ? 0.88 : 1 }],
  shadowColor: '#e65d2d',
  shadowOffset: { width: 0, height: 0 },
  shadowOpacity: pressed ? 0.5 : 0,
  shadowRadius: pressed ? 10 : 0,
  elevation: pressed ? 8 : 0,
});

type ChatHeaderProps = {
  onSidebarPress: () => void;
  onSettingsPress: () => void;
  socketStatus: SocketStatus;
  onReconnect: () => void;
  // Repo props
  repos?: RepoConfig[];
  activeRepo?: RepoConfig | null;
  onSelectRepo?: (repoId: string) => void;
};

export function ChatHeader({
  onSidebarPress,
  onSettingsPress,
  socketStatus,
  onReconnect,
  repos = [],
  activeRepo,
  onSelectRepo,
}: ChatHeaderProps) {
  const [showRepoMenu, setShowRepoMenu] = useState(false);

  return (
    <View className="relative">
      <View className="flex-row items-center justify-between px-4 py-3">
        <Pressable
          onPress={onSidebarPress}
          style={pressStyle}
          className="size-10 rounded-[10px] bg-bg-button items-center justify-center"
        >
          <Text className="text-[13px] font-bold text-text-secondary">VH</Text>
        </Pressable>

        {/* Center: Repo selector or connection status */}
        {repos.length > 0 ? (
          <Pressable
            onPress={() => setShowRepoMenu(!showRepoMenu)}
            className="flex-row items-center gap-1.5 px-3 py-1.5 rounded-lg bg-bg-button"
          >
            <Text className="text-[11px] text-accent">◇</Text>
            <Text className="text-[12px] font-medium text-text-primary" numberOfLines={1}>
              {activeRepo?.name ?? 'Select Repo'}
            </Text>
            <Text className="text-[10px] text-text-secondary">▼</Text>
          </Pressable>
        ) : (
          <ConnectionStatus status={socketStatus} onReconnect={onReconnect} />
        )}

        <Pressable
          onPress={onSettingsPress}
          style={pressStyle}
          className="size-10 items-center justify-center"
        >
          <Text className="text-text-secondary text-lg">&#9881;</Text>
        </Pressable>
      </View>

      {/* Repo dropdown menu */}
      {showRepoMenu && repos.length > 0 && (
        <View className="absolute top-14 left-1/2 -translate-x-1/2 z-50 bg-bg-modal rounded-lg border border-border-subtle shadow-lg min-w-[200px]">
          {repos.map((repo, i) => (
            <Pressable
              key={repo.id}
              onPress={() => {
                onSelectRepo?.(repo.id);
                setShowRepoMenu(false);
              }}
              className={`flex-row items-center gap-2 px-3 py-2.5 ${
                i < repos.length - 1 ? 'border-b border-border-subtle' : ''
              } ${activeRepo?.id === repo.id ? 'bg-accent/10' : ''}`}
            >
              <Text className={activeRepo?.id === repo.id ? 'text-accent text-sm' : 'text-text-secondary text-sm'}>
                {activeRepo?.id === repo.id ? '★' : '◇'}
              </Text>
              <View className="flex-1">
                <Text className="text-[13px] font-medium text-text-primary">{repo.name}</Text>
                <Text className="text-[10px] text-text-secondary" numberOfLines={1}>
                  {repo.path}
                </Text>
              </View>
            </Pressable>
          ))}
        </View>
      )}
    </View>
  );
}
