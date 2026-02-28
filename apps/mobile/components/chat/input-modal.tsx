import { useState } from 'react';
import { View, Text, TextInput, Pressable, ScrollView } from '@/src/tw';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { ModeSelector } from './mode-selector';

const pressStyle = ({ pressed }: { pressed: boolean }) => ({
  opacity: pressed ? 0.85 : 1,
  transform: [{ scale: pressed ? 0.88 : 1 }],
  shadowColor: '#e65d2d',
  shadowOffset: { width: 0, height: 0 },
  shadowOpacity: pressed ? 0.5 : 0,
  shadowRadius: pressed ? 10 : 0,
  elevation: pressed ? 8 : 0,
});

type InputModalProps = {
  onSend: (text: string) => void;
  onAttach?: () => void;
  onMicPress?: () => void;
};

export function InputModal({ onSend, onAttach, onMicPress }: InputModalProps) {
  const [text, setText] = useState('');
  const [mode, setMode] = useState<'plan' | 'build'>('build');
  const [attachments, setAttachments] = useState<string[]>([]);

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setText('');
    setAttachments([]);
  };

  return (
    <View className="px-4 pb-2">
      <View className="bg-bg-modal border border-border-soft rounded-2xl px-3.5 pt-3 pb-2.5">
        {/* Attachments */}
        {attachments.length > 0 && (
          <ScrollView
            horizontal
            className="mb-2.5"
            contentContainerClassName="flex-row gap-1.5"
          >
            {attachments.map((attachment, i) => (
              <View key={i} className="relative bg-bg-button rounded-xl overflow-hidden w-[100px] h-[100px] items-center justify-center">
                <Text className="text-[11px] text-text-secondary">{attachment}</Text>
                <Pressable className="absolute top-1.5 right-1.5 size-5 rounded-full bg-white items-center justify-center">
                  <IconSymbol name="xmark" size={12} color="#000" />
                </Pressable>
              </View>
            ))}
          </ScrollView>
        )}

        {/* Delimiter */}
        {attachments.length > 0 && (
          <View className="h-px bg-border-soft mb-2.5" />
        )}

        {/* Prompt input */}
        <TextInput
          className="text-[15px] text-text-primary min-h-[28px] mb-2.5"
          placeholder='Ask anything...'
          placeholderTextColor="#b9b9ba"
          value={text}
          onChangeText={setText}
          onSubmitEditing={handleSend}
          multiline
        />

        {/* Bottom row: add, mode ... mic, send */}
        <View className="flex-row items-center">
          <Pressable
            onPress={onAttach}
            style={pressStyle}
            className="size-[34px] rounded-lg bg-bg-button items-center justify-center"
          >
            <IconSymbol name="plus" size={20} color="#e5e5e5" />
          </Pressable>
          <View className="ml-2">
            <ModeSelector mode={mode} onModeChange={setMode} />
          </View>
          <View className="flex-1" />
          <Pressable
            onPress={onMicPress}
            style={pressStyle}
            className="size-9 items-center justify-center"
          >
            <IconSymbol name="mic.fill" size={20} color="#b9b9ba" />
          </Pressable>
          <Pressable
            onPress={handleSend}
            style={pressStyle}
            className="size-9 rounded-[10px] bg-accent items-center justify-center ml-1.5"
          >
            <IconSymbol name="arrow.up" size={20} color="#fff" />
          </Pressable>
        </View>
      </View>
    </View>
  );
}
