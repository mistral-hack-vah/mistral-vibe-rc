import { useEffect, useRef } from 'react';
import { Animated, Dimensions, TouchableWithoutFeedback } from 'react-native';
import { View, Text, Pressable, ScrollView, TextInput } from '@/src/tw';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

const SIDEBAR_WIDTH = 280;

type SidebarProps = {
  visible: boolean;
  onClose: () => void;
};

const PROJECTS = [
  { id: '1', name: 'Jest', sessions: [] },
  { id: '2', name: 'test', sessions: [] },
];

const SESSIONS = [
  { id: '1', title: 'Python Summarizer', group: 'Today', active: true },
  { id: '2', title: 'Python Function Creation', group: 'Today' },
  { id: '3', title: 'French Language Assistance', group: 'Today' },
  { id: '4', title: 'Implement new feature', group: 'Previous 7 days' },
  { id: '5', title: 'Python: Subsequence Count', group: 'Previous 30 days' },
];

const SESSION_GROUPS = ['Today', 'Previous 7 days', 'Previous 30 days'];

export function Sidebar({ visible, onClose }: SidebarProps) {
  const insets = useSafeAreaInsets();

  const translateX = useRef(new Animated.Value(-SIDEBAR_WIDTH)).current;
  const overlayOpacity = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (visible) {
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
          toValue: -SIDEBAR_WIDTH,
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

      {/* Drawer */}
      <Animated.View
        style={{
          position: 'absolute',
          top: 0,
          bottom: 0,
          left: 0,
          width: SIDEBAR_WIDTH,
          backgroundColor: '#111115',
          transform: [{ translateX }],
          paddingTop: insets.top + 8,
          paddingBottom: insets.bottom + 8,
        }}
      >
        <View className="flex-1">
          {/* Search bar */}
          <View className="px-4 pt-2 pb-3">
            <View className="flex-row items-center bg-bg-button rounded-input px-3 h-10">
              <IconSymbol name="magnifyingglass" size={18} color="#b9b9ba" />
              <TextInput
                className="flex-1 ml-2 text-sm text-text-primary"
                placeholder="Search"
                placeholderTextColor="#b9b9ba"
              />
            </View>
          </View>

          {/* Scrollable content */}
          <ScrollView className="flex-1" contentContainerClassName="pb-4">
            {/* Projects section */}
            <View className="px-4 pt-2 pb-1">
              <Text className="text-xs font-semibold text-accent uppercase tracking-wider">
                Projects
              </Text>
            </View>

            <Pressable className="flex-row items-center gap-3 px-4 py-2">
              <IconSymbol name="folder.badge.plus" size={20} color="#b9b9ba" />
              <Text className="text-sm text-text-secondary">New project</Text>
            </Pressable>

            {PROJECTS.map((project) => (
              <Pressable
                key={project.id}
                className="flex-row items-center px-4 py-2"
              >
                <IconSymbol name="folder" size={20} color="#b9b9ba" />
                <Text className="flex-1 ml-3 text-sm text-text-primary">
                  {project.name}
                </Text>
                <IconSymbol name="chevron.right" size={16} color="#b9b9ba" />
              </Pressable>
            ))}

            {/* Sessions grouped by date */}
            {SESSION_GROUPS.map((group) => {
              const groupSessions = SESSIONS.filter((s) => s.group === group);
              if (groupSessions.length === 0) return null;

              return (
                <View key={group} className="mt-4">
                  <Text className="px-4 pb-1 text-xs text-text-secondary">
                    {group}
                  </Text>
                  {groupSessions.map((session) => (
                    <Pressable
                      key={session.id}
                      className={`mx-2 px-3 py-2 rounded-button ${
                        session.active ? 'bg-bg-button' : ''
                      }`}
                    >
                      <Text
                        className="text-sm text-text-primary"
                        numberOfLines={1}
                      >
                        {session.title}
                      </Text>
                    </Pressable>
                  ))}
                </View>
              );
            })}

            {/* End indicator */}
            <View className="items-center py-6">
              <Text className="text-xs text-text-secondary">
                ᵔ^._.^ᵔ You've reached the end!
              </Text>
            </View>
          </ScrollView>

          {/* Bottom pinned section */}
          <View className="border-t border-border-subtle" />

          <View className="px-3 pt-3 pb-1">
            <Pressable
              onPress={onClose}
              className="flex-row items-center justify-center gap-2 bg-accent rounded-button py-2.5"
            >
              <IconSymbol name="bubble.left" size={18} color="#fff" />
              <Text className="text-sm font-semibold text-white">
                New Thread
              </Text>
            </Pressable>
          </View>

          {/* Settings row */}
          <View className="flex-row items-center px-4 py-3">
            <View className="w-8 h-8 rounded-full bg-bg-button items-center justify-center">
              <Text className="text-xs font-bold text-text-primary">VR</Text>
            </View>
            <View className="flex-1 ml-3">
              <Text className="text-sm font-semibold text-text-primary">
                Personal
              </Text>
              <Text className="text-xs text-text-secondary">
                Le Chat Free
              </Text>
            </View>
            <Pressable className="p-1">
              <IconSymbol name="ellipsis" size={20} color="#b9b9ba" />
            </Pressable>
          </View>
        </View>
      </Animated.View>
    </View>
  );
}
