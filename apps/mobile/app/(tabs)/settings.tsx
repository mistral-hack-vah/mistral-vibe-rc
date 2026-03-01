import { View, Text, Pressable, ScrollView, TextInput } from '@/src/tw';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useState, useEffect, useCallback } from 'react';
import * as api from '@/hooks/api-client';
import type { RepoConfig } from '@/hooks/api-client';

const SETTINGS_ITEMS = [
  { label: 'Memories', value: 'Disabled' },
  { label: 'Instructions', value: 'Default' },
  { label: 'Connectors' },
  { label: 'Libraries' },
];

export default function ExploreScreen() {
  const insets = useSafeAreaInsets();
  const [repos, setRepos] = useState<RepoConfig[]>([]);
  const [newRepoPath, setNewRepoPath] = useState('');
  const [isAddingRepo, setIsAddingRepo] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load repos on mount
  useEffect(() => {
    api.getRepos().then(setRepos).catch(console.error);
  }, []);

  const handleAddRepo = useCallback(async () => {
    if (!newRepoPath.trim()) return;
    setError(null);
    setIsAddingRepo(true);
    try {
      const newRepo = await api.addRepo(newRepoPath.trim());
      setRepos((prev) => [...prev, newRepo]);
      setNewRepoPath('');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to add repository');
    } finally {
      setIsAddingRepo(false);
    }
  }, [newRepoPath]);

  const handleRemoveRepo = useCallback(async (repoId: string) => {
    try {
      await api.removeRepo(repoId);
      setRepos((prev) => prev.filter((r) => r.id !== repoId));
    } catch (e) {
      console.error('Failed to remove repo:', e);
    }
  }, []);

  const handleSetDefault = useCallback(async (repoId: string) => {
    try {
      await api.setDefaultRepo(repoId);
      setRepos((prev) =>
        prev.map((r) => ({
          ...r,
          is_default: r.id === repoId,
        }))
      );
    } catch (e) {
      console.error('Failed to set default repo:', e);
    }
  }, []);

  return (
    <View className="flex-1 bg-bg-base" style={{ paddingTop: insets.top }}>
      {/* Header */}
      <View className="flex-row items-center px-4 py-3.5 border-b border-border-subtle">
        <Text className="flex-1 text-center text-[15px] font-bold text-text-primary">
          Settings
        </Text>
      </View>

      <ScrollView className="flex-1" contentContainerClassName="p-3.5">
        {/* Git Repositories section */}
        <Text className="text-[11px] font-semibold tracking-widest uppercase text-text-secondary px-1 mb-2.5">
          Git Repositories
        </Text>
        <View className="bg-bg-modal rounded-card border border-border-subtle mb-5">
          {repos.length === 0 ? (
            <View className="px-3.5 py-4">
              <Text className="text-[13px] text-text-secondary text-center">
                No repositories configured
              </Text>
            </View>
          ) : (
            repos.map((repo, i) => (
              <View
                key={repo.id}
                className={`flex-row items-center justify-between px-3.5 py-3 ${
                  i < repos.length - 1 ? 'border-b border-border-subtle' : ''
                }`}>
                <Pressable
                  className="flex-1 flex-row items-center gap-2.5"
                  onPress={() => handleSetDefault(repo.id)}>
                  <View
                    className={`size-7.5 rounded-lg items-center justify-center ${
                      repo.is_default ? 'bg-accent/20' : 'bg-accent-secondary/15'
                    }`}>
                    <Text className={repo.is_default ? 'text-accent text-sm' : 'text-accent-secondary text-sm'}>
                      {repo.is_default ? '★' : '◇'}
                    </Text>
                  </View>
                  <View className="flex-1">
                    <Text className="text-[13px] font-medium text-text-primary">{repo.name}</Text>
                    <Text className="text-[11px] text-text-secondary" numberOfLines={1}>
                      {repo.path}
                    </Text>
                  </View>
                </Pressable>
                <Pressable
                  className="p-2"
                  onPress={() => handleRemoveRepo(repo.id)}>
                  <Text className="text-red-500 text-sm">✕</Text>
                </Pressable>
              </View>
            ))
          )}

          {/* Add repo input */}
          <View className="px-3.5 py-3 border-t border-border-subtle">
            <View className="flex-row items-center gap-2">
              <TextInput
                className="flex-1 bg-bg-base rounded-lg px-3 py-2 text-[13px] text-text-primary border border-border-subtle"
                placeholder="Enter repository path..."
                placeholderTextColor="#666"
                value={newRepoPath}
                onChangeText={setNewRepoPath}
                editable={!isAddingRepo}
              />
              <Pressable
                className={`px-4 py-2 rounded-lg ${
                  isAddingRepo || !newRepoPath.trim() ? 'bg-accent/50' : 'bg-accent'
                }`}
                onPress={handleAddRepo}
                disabled={isAddingRepo || !newRepoPath.trim()}>
                <Text className="text-white text-[13px] font-medium">
                  {isAddingRepo ? '...' : 'Add'}
                </Text>
              </Pressable>
            </View>
            {error && (
              <Text className="text-red-500 text-[11px] mt-2">{error}</Text>
            )}
          </View>
        </View>

        {/* Intelligence section */}
        <Text className="text-[11px] font-semibold tracking-widest uppercase text-text-secondary px-1 mb-2.5">
          Intelligence
        </Text>
        <View className="bg-bg-modal rounded-card border border-border-subtle mb-5">
          {SETTINGS_ITEMS.map((item, i) => (
            <Pressable
              key={item.label}
              className={`flex-row items-center justify-between px-3.5 py-3 ${i < SETTINGS_ITEMS.length - 1 ? 'border-b border-border-subtle' : ''
                }`}>
              <View className="flex-row items-center gap-2.5">
                <View className="size-7.5 rounded-lg bg-accent-secondary/15 items-center justify-center">
                  <Text className="text-accent-secondary text-sm">&#9881;</Text>
                </View>
                <Text className="text-[13px] font-medium text-text-primary">{item.label}</Text>
              </View>
              <Text className="text-[12px] text-text-secondary">
                {item.value ? `${item.value} ›` : '›'}
              </Text>
            </Pressable>
          ))}
        </View>

        {/* Account section */}
        <Text className="text-[11px] font-semibold tracking-widest uppercase text-text-secondary px-1 mb-2.5">
          Account
        </Text>
        <View className="bg-bg-modal rounded-card border border-border-subtle">
          <View className="flex-row items-center justify-between px-3.5 py-3 border-b border-border-subtle">
            <Text className="text-[13px] text-text-secondary">Email</Text>
            <Text className="text-[12px] text-text-secondary font-mono">user@email.com</Text>
          </View>
          <View className="flex-row items-center justify-between px-3.5 py-3 border-b border-border-subtle">
            <Text className="text-[13px] text-text-secondary">Subscription</Text>
            <Text className="text-[12px] text-text-secondary">Thread Free</Text>
          </View>
          <Pressable className="px-3.5 py-3">
            <Text className="text-[13px] text-accent font-medium">Upgrade now</Text>
          </Pressable>
        </View>

        {/* Pro banner */}
        <View className="mt-5 rounded-card overflow-hidden">
          <View className="bg-bg-dark p-6">
            <Text className="text-lg font-bold text-text-primary mb-1">Le Chat Pro</Text>
            <Text className="text-[26px] font-bold text-text-primary mb-4">
              $19.99<Text className="text-sm font-medium">/mo</Text>
            </Text>
            {['More messages and web searches', 'Extended thinking', 'Deep research reports', 'Up to 15GB storage'].map(
              (feature) => (
                <View key={feature} className="flex-row items-center gap-2 mb-2">
                  <Text className="text-accent text-sm">✓</Text>
                  <Text className="text-[13px] text-text-primary/90">{feature}</Text>
                </View>
              )
            )}
            <Pressable className="mt-4 bg-accent rounded-button py-3 items-center">
              <Text className="text-white font-semibold text-sm">Upgrade to Pro</Text>
            </Pressable>
          </View>
        </View>

        {/* Connectors preview */}
        <Text className="text-[11px] font-semibold tracking-widest uppercase text-text-secondary px-1 mt-5 mb-2.5">
          Connectors
        </Text>
        <View className="bg-bg-modal rounded-card border border-border-subtle">
          {['Gmail', 'Google Calendar', 'Google Drive'].map((name, i) => (
            <Pressable
              key={name}
              className={`flex-row items-center justify-between px-3.5 py-3 ${i < 2 ? 'border-b border-border-subtle' : ''
                }`}>
              <Text className="text-[13px] font-medium text-text-primary">{name}</Text>
              <View className="size-6 rounded-md bg-accent-blue/15 items-center justify-center">
                <Text className="text-accent-blue text-xs">+</Text>
              </View>
            </Pressable>
          ))}
        </View>
      </ScrollView>
    </View>
  );
}
