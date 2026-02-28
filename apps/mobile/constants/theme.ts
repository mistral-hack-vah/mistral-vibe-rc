import { Platform } from 'react-native';

export const Colors = {
  light: {
    text: '#ffffff',
    background: '#18181b',
    tint: '#e65d2d',
    icon: '#b9b9ba',
    tabIconDefault: '#b9b9ba',
    tabIconSelected: '#e65d2d',
  },
  dark: {
    text: '#ffffff',
    background: '#18181b',
    tint: '#e65d2d',
    icon: '#b9b9ba',
    tabIconDefault: '#b9b9ba',
    tabIconSelected: '#e65d2d',
  },
};

export const Fonts = Platform.select({
  ios: {
    sans: 'system-ui',
    serif: 'ui-serif',
    rounded: 'ui-rounded',
    mono: 'ui-monospace',
  },
  default: {
    sans: 'normal',
    serif: 'serif',
    rounded: 'normal',
    mono: 'monospace',
  },
  web: {
    sans: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
    serif: "Georgia, 'Times New Roman', serif",
    rounded: "'SF Pro Rounded', 'Hiragino Maru Gothic ProN', Meiryo, 'MS PGothic', sans-serif",
    mono: "SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace",
  },
});
