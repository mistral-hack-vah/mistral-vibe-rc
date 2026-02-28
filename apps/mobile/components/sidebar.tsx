import { useEffect, useRef } from 'react';
import { Animated, Dimensions, TouchableWithoutFeedback } from 'react-native';
import { View, Text, Pressable } from '@/src/tw';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useRouter, usePathname } from 'expo-router';

const SIDEBAR_WIDTH = 280;
const { width: SCREEN_WIDTH } = Dimensions.get('window');

type SidebarProps = {
  visible: boolean;
  onClose: () => void;
};

const NAV_ITEMS = [
  { label: 'Home', icon: 'house.fill' as const, route: '/(tabs)' as const },
  { label: 'Settings', icon: 'gearshape.fill' as const, route: '/(tabs)/explore' as const },
];

export function Sidebar({ visible, onClose }: SidebarProps) {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const pathname = usePathname();

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

  const handleNav = (route: string) => {
    router.navigate(route as any);
    onClose();
  };

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
          paddingTop: insets.top + 16,
          paddingBottom: insets.bottom + 16,
        }}
      >
        {/* App title */}
        <View className="px-5 mb-6">
          <Text className="text-[22px] font-bold text-accent tracking-tight">
            Le Thread
          </Text>
          <Text className="text-[11px] text-text-secondary mt-0.5">
            Vibe on the go
          </Text>
        </View>

        {/* Nav items */}
        <View className="px-3 gap-1">
          {NAV_ITEMS.map((item) => {
            const isActive =
              (item.route === '/(tabs)' && pathname === '/') ||
              (item.route === '/(tabs)/explore' && pathname === '/explore');

            return (
              <Pressable
                key={item.label}
                onPress={() => handleNav(item.route)}
                className={`flex-row items-center gap-3 px-3 py-2.5 rounded-button ${
                  isActive ? 'bg-accent/10' : ''
                }`}
              >
                <IconSymbol
                  name={item.icon}
                  size={20}
                  color={isActive ? '#e65d2d' : '#b9b9ba'}
                />
                <Text
                  className={`text-[14px] font-medium ${
                    isActive ? 'text-accent' : 'text-text-secondary'
                  }`}
                >
                  {item.label}
                </Text>
              </Pressable>
            );
          })}
        </View>

        {/* New chat button */}
        <View className="px-3 mt-4">
          <Pressable
            onPress={onClose}
            className="flex-row items-center gap-2.5 bg-accent rounded-button px-3.5 py-2.5"
          >
            <IconSymbol name="plus" size={18} color="#fff" />
            <Text className="text-[13px] font-semibold text-white">
              New Thread
            </Text>
          </Pressable>
        </View>
      </Animated.View>
    </View>
  );
}
