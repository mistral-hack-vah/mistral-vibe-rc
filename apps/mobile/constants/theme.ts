import { Platform } from 'react-native';

export const Colors = {
  light: {
    text: '#F4F4F4',
    background: '#080808',
    tint: '#F5631A',
    icon: '#9A9A9A',
    tabIconDefault: '#5C5C5C',
    tabIconSelected: '#F5631A',
  },
  dark: {
    text: '#F4F4F4',
    background: '#080808',
    tint: '#F5631A',
    icon: '#9A9A9A',
    tabIconDefault: '#5C5C5C',
    tabIconSelected: '#F5631A',
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
