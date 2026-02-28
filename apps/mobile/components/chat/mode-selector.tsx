import { useState, useRef, useEffect } from 'react';
import { Animated, Modal, TouchableWithoutFeedback } from 'react-native';
import { View, Text, Pressable } from '@/src/tw';
import { IconSymbol } from '@/components/ui/icon-symbol';

const pressStyle = ({ pressed }: { pressed: boolean }) => ({
  opacity: pressed ? 0.85 : 1,
  transform: [{ scale: pressed ? 0.92 : 1 }],
  shadowColor: '#e65d2d',
  shadowOffset: { width: 0, height: 0 },
  shadowOpacity: pressed ? 0.5 : 0,
  shadowRadius: pressed ? 10 : 0,
  elevation: pressed ? 8 : 0,
});

type ModeSelectorProps = {
  mode: 'plan' | 'build';
  onModeChange: (mode: 'plan' | 'build') => void;
};

const MODE_CONFIG = {
  plan: {
    label: 'Plan',
    icon: 'lightbulb.fill' as const,
    color: '#63abe1',       // tertiary accent
    bgClass: 'bg-accent-tertiary/15',
    textClass: 'text-accent-tertiary',
  },
  build: {
    label: 'Build',
    icon: 'hammer.fill' as const,
    color: '#f4b33e',       // secondary accent
    bgClass: 'bg-accent-secondary/15',
    textClass: 'text-accent-secondary',
  },
};

export function ModeSelector({ mode, onModeChange }: ModeSelectorProps) {
  const [open, setOpen] = useState(false);
  const [buttonLayout, setButtonLayout] = useState({ x: 0, y: 0, width: 0, height: 0 });
  const buttonRef = useRef<any>(null);
  const current = MODE_CONFIG[mode];

  const handleSelect = (selected: 'plan' | 'build') => {
    onModeChange(selected);
    setOpen(false);
  };

  const measureButton = () => {
    buttonRef.current?.measureInWindow((x: number, y: number, width: number, height: number) => {
      setButtonLayout({ x, y, width, height });
    });
  };

  return (
    <>
      <Pressable
        ref={buttonRef}
        onPress={() => {
          measureButton();
          setOpen(true);
        }}
        style={pressStyle}
        className={`flex-row items-center gap-1.5 h-[34px] px-2.5 rounded-lg ${current.bgClass}`}
      >
        <IconSymbol name={current.icon} size={14} color={current.color} />
        <Text className={`text-[12px] font-semibold ${current.textClass}`}>
          {current.label}
        </Text>
        <IconSymbol name="chevron.down" size={12} color={current.color} />
      </Pressable>

      <Modal visible={open} transparent animationType="fade">
        <TouchableWithoutFeedback onPress={() => setOpen(false)}>
          <View className="flex-1">
            <View
              className="absolute bg-bg-modal border border-border-soft rounded-button overflow-hidden"
              style={{
                left: buttonLayout.x,
                top: buttonLayout.y - 2 - 2 * 38, // position above button
                minWidth: 130,
              }}
            >
              {(['plan', 'build'] as const).map((key) => {
                const cfg = MODE_CONFIG[key];
                const isSelected = key === mode;
                return (
                  <Pressable
                    key={key}
                    onPress={() => handleSelect(key)}
                    style={pressStyle}
                    className={`flex-row items-center gap-2.5 px-3 py-2.5 ${
                      isSelected ? cfg.bgClass : ''
                    }`}
                  >
                    <IconSymbol name={cfg.icon} size={16} color={cfg.color} />
                    <Text
                      className={`text-[13px] font-medium ${
                        isSelected ? cfg.textClass : 'text-text-primary'
                      }`}
                    >
                      {cfg.label}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
          </View>
        </TouchableWithoutFeedback>
      </Modal>
    </>
  );
}
