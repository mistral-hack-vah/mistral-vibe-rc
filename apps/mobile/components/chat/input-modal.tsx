import { useState } from 'react';
import { View, Text, TextInput, Pressable, ScrollView } from '@/src/tw';
import { Image } from '@/src/tw/image';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { ModeSelector } from './mode-selector';
import * as ImagePicker from 'expo-image-picker';
import type { Attachment } from './types';

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
  onSend: (text: string, attachments: Attachment[]) => void;
  onMicPress?: () => void;
};

export function InputModal({ onSend, onMicPress }: InputModalProps) {
  const [text, setText] = useState('');
  const [mode, setMode] = useState<'plan' | 'build'>('plan');
  const [attachments, setAttachments] = useState<Attachment[]>([]);

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed && attachments.length === 0) return;
    onSend(trimmed, attachments);
    setText('');
    setAttachments([]);
  };

  const pickImage = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      allowsMultipleSelection: true,
      quality: 0.8,
    });

    if (!result.canceled && result.assets.length > 0) {
      const newAttachments: Attachment[] = result.assets.map((asset) => ({
        uri: asset.uri,
        type: 'image' as const,
        name: asset.fileName ?? 'image.jpg',
        width: asset.width,
        height: asset.height,
      }));
      setAttachments((prev) => [...prev, ...newAttachments]);
    }
  };

  const removeAttachment = (index: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== index));
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
              <View
                key={i}
                className="relative rounded-xl overflow-hidden w-[100px] h-[100px]"
              >
                <Image
                  source={attachment.uri}
                  className="w-full h-full object-cover"
                />
                <Pressable
                  onPress={() => removeAttachment(i)}
                  className="absolute top-1.5 right-1.5 size-5 rounded-full bg-black/60 items-center justify-center"
                >
                  <IconSymbol name="xmark" size={10} color="#fff" />
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
          placeholder="Ask anything..."
          placeholderTextColor="#b9b9ba"
          value={text}
          onChangeText={setText}
          onSubmitEditing={handleSend}
          multiline
        />

        {/* Bottom row: add, mode ... mic, send */}
        <View className="flex-row items-center">
          <Pressable
            onPress={pickImage}
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
