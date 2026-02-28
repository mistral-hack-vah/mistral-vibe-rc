import { useState, useCallback, useRef } from 'react';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withSpring,
  type SharedValue,
} from 'react-native-reanimated';
import { View, Text, TextInput, Pressable, ScrollView } from '@/src/tw';
import { Image } from '@/src/tw/image';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { ModeSelector } from './mode-selector';
import * as ImagePicker from 'expo-image-picker';
import type { Attachment } from './types';
import {
  useAudioRecorder,
  ExpoAudioStreamModule,
  type AudioRecording,
  type RecordingConfig,
} from '@siteed/expo-audio-studio';

const BAR_VARIATIONS = [0.5, 0.9, 1.0, 0.8, 0.6, 0.75];

function VoiceBar({ sv }: { sv: SharedValue<number> }) {
  const style = useAnimatedStyle(() => ({ height: sv.value }));
  return (
    <Animated.View
      style={[{ flex: 1, borderRadius: 3, backgroundColor: '#7cd659' }, style]}
    />
  );
}

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
  onAudioRecorded?: (recording: AudioRecording) => void;
};

export function InputModal({ onSend, onAudioRecorded }: InputModalProps) {
  const [text, setText] = useState('');
  const [mode, setMode] = useState<'plan' | 'build'>('plan');
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [autosend, setAutosend] = useState(true);

  const b0 = useSharedValue(4);
  const b1 = useSharedValue(4);
  const b2 = useSharedValue(4);
  const b3 = useSharedValue(4);
  const b4 = useSharedValue(4);
  const b5 = useSharedValue(4);
  const barValues = [b0, b1, b2, b3, b4, b5];

  const recordingConfig = useRef<RecordingConfig>({
    interval: 100,
    enableProcessing: false,
    sampleRate: 44100,
    channels: 1,
    encoding: 'pcm_16bit',
    output: {
      primary: { enabled: true },
      compressed: { enabled: false, format: 'aac', bitrate: 128000 },
    },
    autoResumeAfterInterruption: false,
    bufferDurationSeconds: 0.1,
    onAudioStream: async (event) => {
      let amp = 0;
      try {
        if (typeof event.data !== 'string') {
          const data = event.data as unknown as Int16Array;
          let sum = 0;
          for (let i = 0; i < data.length; i++) sum += (data[i] / 32768) ** 2;
          amp = Math.min(1, Math.sqrt(sum / data.length) * 6);
        } else {
          const binary = atob(event.data);
          const bytes = new Uint8Array(binary.length);
          for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
          const samples = new Int16Array(bytes.buffer);
          let sum = 0;
          for (let i = 0; i < samples.length; i++) sum += (samples[i] / 32768) ** 2;
          amp = Math.min(1, Math.sqrt(sum / samples.length) * 6);
        }
      } catch {
        return;
      }
      barValues.forEach((sv, i) => {
        sv.value = withSpring(Math.max(4, amp * 56 * BAR_VARIATIONS[i]), {
          damping: 15,
          stiffness: 150,
        });
      });
    },
  }).current;

  const { startRecording, stopRecording, isRecording } = useAudioRecorder();

  const resetBars = () => barValues.forEach((sv) => (sv.value = withSpring(4)));

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed && attachments.length === 0) return;
    onSend(trimmed, attachments);
    setText('');
    setAttachments([]);
  };

  const handleMicPress = useCallback(async () => {
    const { status } = await ExpoAudioStreamModule.requestPermissionsAsync();
    if (status !== 'granted') return;
    await startRecording(recordingConfig);
  }, [startRecording]);

  const handleCancelRecording = useCallback(async () => {
    await stopRecording();
    resetBars();
  }, [stopRecording]);

  const handleSendRecording = useCallback(async () => {
    const result = await stopRecording();
    resetBars();
    onAudioRecorded?.(result);
  }, [stopRecording, onAudioRecorded]);

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

  // ─── Recording UI ───
  if (isRecording) {
    return (
      <View className="px-4 pb-2">
        <View className="bg-bg-modal border border-border-soft rounded-2xl px-3.5 pt-4 pb-3">
          <View style={{ flexDirection: 'row', alignItems: 'center', height: 64, gap: 6, marginBottom: 12 }}>
            {barValues.map((sv, i) => (
              <VoiceBar key={i} sv={sv} />
            ))}
          </View>

          <View className="flex-row items-center">
            <Pressable onPress={handleCancelRecording} style={pressStyle} className="size-[44px] rounded-xl bg-bg-button items-center justify-center">
              <IconSymbol name="xmark" size={18} color="#b9b9ba" />
            </Pressable>

            <View className="flex-1 flex-row items-center justify-center">
              <Text className="text-text-primary text-[15px] font-medium mr-2">Autosend</Text>
              <Pressable
                onPress={() => setAutosend((v) => !v)}
                style={{
                  backgroundColor: autosend ? 'rgba(230, 93, 45, 0.25)' : 'rgba(255,255,255,0.1)',
                  paddingHorizontal: 8,
                  paddingVertical: 3,
                  borderRadius: 6,
                }}
              >
                <Text style={{ color: autosend ? '#e65d2d' : '#b9b9ba', fontSize: 13, fontWeight: '700' }}>
                  {autosend ? 'ON' : 'OFF'}
                </Text>
              </Pressable>
            </View>

            <Pressable onPress={handleSendRecording} style={pressStyle} className="size-[44px] rounded-xl bg-accent items-center justify-center">
              <IconSymbol name="arrow.up" size={20} color="#fff" />
            </Pressable>
          </View>
        </View>
      </View>
    );
  }

  // ─── Default text input UI ───
  return (
    <View className="px-4 pb-2">
      <View className="bg-bg-modal border border-border-soft rounded-2xl px-3.5 pt-3 pb-2.5">
        {attachments.length > 0 && (
          <ScrollView horizontal className="mb-2.5" contentContainerClassName="flex-row gap-1.5">
            {attachments.map((attachment, i) => (
              <View key={i} className="relative rounded-xl overflow-hidden w-[100px] h-[100px]">
                <Image source={attachment.uri} className="w-full h-full object-cover" />
                <Pressable onPress={() => removeAttachment(i)} className="absolute top-1.5 right-1.5 size-5 rounded-full bg-black/60 items-center justify-center">
                  <IconSymbol name="xmark" size={10} color="#fff" />
                </Pressable>
              </View>
            ))}
          </ScrollView>
        )}

        {attachments.length > 0 && <View className="h-px bg-border-soft mb-2.5" />}

        <TextInput
          className="text-[15px] text-text-primary min-h-[28px] mb-2.5"
          placeholder="Ask anything..."
          placeholderTextColor="#b9b9ba"
          value={text}
          onChangeText={setText}
          onSubmitEditing={handleSend}
          multiline
        />

        <View className="flex-row items-center">
          <Pressable onPress={pickImage} style={pressStyle} className="size-[34px] rounded-lg bg-bg-button items-center justify-center">
            <IconSymbol name="plus" size={20} color="#e5e5e5" />
          </Pressable>
          <View className="ml-2">
            <ModeSelector mode={mode} onModeChange={setMode} />
          </View>
          <View className="flex-1" />
          <Pressable onPress={handleMicPress} style={pressStyle} className="size-9 items-center justify-center">
            <IconSymbol name="mic.fill" size={20} color="#b9b9ba" />
          </Pressable>
          <Pressable onPress={handleSend} style={pressStyle} className="size-9 rounded-[10px] bg-accent items-center justify-center ml-1.5">
            <IconSymbol name="arrow.up" size={20} color="#fff" />
          </Pressable>
        </View>
      </View>
    </View>
  );
}
