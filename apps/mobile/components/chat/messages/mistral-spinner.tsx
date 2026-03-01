import { View } from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withRepeat,
  withTiming,
  withDelay,
  Easing,
} from 'react-native-reanimated';
import { useEffect } from 'react';

// Mistral "M" logo bars — two wide top bars + three narrow stem bars
// Pulsing opacity animation staggered by 0.15s per bar
const BARS = [
  // top bar
  { x: 0,     y: 0,     w: 1,     h: 0.2,  color: '#FFD800', delay: 0 },
  { x: 0,     y: 0.2,   w: 1,     h: 0.2,  color: '#FFAF00', delay: 150 },
  // stem
  { x: 0.2,   y: 0.4,   w: 0.6,   h: 0.2,  color: '#FF8205', delay: 300 },
  { x: 0.2,   y: 0.6,   w: 0.6,   h: 0.2,  color: '#FA500F', delay: 450 },
  { x: 0.2,   y: 0.8,   w: 0.6,   h: 0.2,  color: '#E10500', delay: 600 },
];

type Props = {
  size?: number;
};

function PulsingBar({
  x, y, w, h, color, delay, size,
}: {
  x: number; y: number; w: number; h: number;
  color: string; delay: number; size: number;
}) {
  const opacity = useSharedValue(0.25);

  useEffect(() => {
    opacity.value = withDelay(
      delay,
      withRepeat(
        withTiming(1, { duration: 600, easing: Easing.inOut(Easing.ease) }),
        -1,
        true, // reverse
      ),
    );
  }, [opacity, delay]);

  const style = useAnimatedStyle(() => ({
    opacity: opacity.value,
  }));

  return (
    <Animated.View
      style={[
        {
          position: 'absolute',
          left: x * size,
          top: y * size,
          width: w * size,
          height: h * size,
          backgroundColor: color,
        },
        style,
      ]}
    />
  );
}

export function MistralSpinner({ size = 20 }: Props) {
  return (
    <View style={{ width: size, height: size }}>
      {BARS.map((bar, i) => (
        <PulsingBar key={i} {...bar} size={size} />
      ))}
    </View>
  );
}
