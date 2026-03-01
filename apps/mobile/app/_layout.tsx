import '@/src/global.css';

import { DarkTheme, ThemeProvider } from '@react-navigation/native';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import 'react-native-reanimated';
import { PermissionProvider } from '@/contexts/permission-context';

const MistralDarkTheme = {
  ...DarkTheme,
  colors: {
    ...DarkTheme.colors,
    primary: '#e65d2d',
    background: '#18181b',
    card: '#18181b',
    text: '#ffffff',
    border: 'rgba(255,255,255,0.07)',
    notification: '#e65d2d',
  },
};

export const unstable_settings = {
  anchor: '(tabs)',
};

export default function RootLayout() {
  return (
    <PermissionProvider>
      <ThemeProvider value={MistralDarkTheme}>
        <Stack>
          <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
          <Stack.Screen
            name="modal"
            options={{
              presentation: 'modal',
              title: 'Modal',
              headerStyle: { backgroundColor: '#222225' },
              headerTintColor: '#ffffff',
            }}
          />
        </Stack>
        <StatusBar style="light" />
      </ThemeProvider>
    </PermissionProvider>
  );
}
