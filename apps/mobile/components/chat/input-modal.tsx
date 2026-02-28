import { IconSymbol } from '@/components/ui/icon-symbol';
import { useAudioSocket } from '@/hooks/use-audio-socket';
import { useControlSocket } from '@/hooks/use-control-socket';
import { Pressable, ScrollView, Text, TextInput, View } from '@/src/tw';
import { Image } from '@/src/tw/image';
import {
  ExpoAudioStreamModule,
  useAudioRecorder,
  type AudioRecording,
  type RecordingConfig,
} from '@siteed/expo-audio-studio';
import * as ImagePicker from 'expo-image-picker';
import { LinearGradient } from 'expo-linear-gradient';
import { useCallback, useEffect, useRef, useState } from 'react';
import Animated, {
  cancelAnimation,
  makeMutable,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withSpring,
  withTiming,
  type SharedValue,
} from 'react-native-reanimated';
import { ModeSelector } from './mode-selector';
import type { Attachment } from './types';

const BAR_COUNT = 14;
const BAR_VARIATIONS = Array.from({ length: BAR_COUNT }, (_, i) => {
  return 0.45 + 0.55 * Math.sin((i / (BAR_COUNT - 1)) * Math.PI);
});

function VoiceBar({ sv }: { sv: SharedValue<number> }) {
  const style = useAnimatedStyle(() => ({
    height: sv.value,
    shadowOpacity: sv.value > 12 ? 0.75 : 0,
    shadowRadius: sv.value > 12 ? 6 : 0,
  }));
  return (
    <Animated.View
      style={[{
        // flex: 1,
        width: 6,
        borderRadius: 17,
        overflow: 'hidden',
        shadowColor: '#ADFF2F',
        shadowOffset: { width: 0, height: 0 },
      }, style]}
    >
      <LinearGradient
        colors={['#ADFF2F', '#228B22']}
        style={{ flex: 1 }}
      />
    </Animated.View>
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

  const bars = useRef(
    Array.from({ length: BAR_COUNT }, () => makeMutable(4))
  ).current;

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
      if (!event.data) return;
      let buffer: ArrayBuffer;
      let amp = 0;
      if (typeof event.data !== 'string') {
        // Web: convert Float32Array to 16-bit PCM
        const pcm = new Int16Array(event.data.length);
        for (let i = 0; i < event.data.length; i++) {
          const s = Math.max(-1, Math.min(1, event.data[i]));
          pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
        }
        buffer = pcm.buffer;

        let sum = 0;
        for (let i = 0; i < pcm.length; i++) sum += (pcm[i] / 32768) ** 2;
        amp = Math.min(1, Math.sqrt(sum / pcm.length) * 6);
      } else {
        // Native: base64-encoded PCM string
        const bin = atob(event.data);
        const bytes = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i++) {
          bytes[i] = bin.charCodeAt(i);
        }
        buffer = bytes.buffer;

        const samples = new Int16Array(bytes.buffer);
        let sum = 0;
        for (let i = 0; i < samples.length; i++) {
          sum += (samples[i] / 32768) ** 2;
        }
        amp = Math.min(1, Math.sqrt(sum / samples.length) * 6);
      }
      // Skip tiny metadata/header chunks — real audio is ≥1000 bytes
      if (buffer.byteLength < 1000) return;
      console.log(`[mic] chunk ${buffer.byteLength} bytes`);
      audioSocket.sendBinary(buffer);

      bars.forEach((sv, i) => {
        sv.value = withSpring(Math.max(4, amp * 56 * BAR_VARIATIONS[i]), {
          damping: 15,
          stiffness: 150,
        });
      });
    },
  }).current;

  const { startRecording, stopRecording, isRecording } = useAudioRecorder();

  const resetBars = useCallback(() => bars.forEach((sv) => (sv.value = withSpring(4))), [bars]);

  const { status: controlStatus } = useControlSocket();
  const audioSocket = useAudioSocket();
  const micDisabled = controlStatus !== 'connected';

  // Auto-connect audio socket as soon as control is established
  useEffect(() => {
    if (controlStatus === 'connected') {
      audioSocket.connect();
    }
  }, [audioSocket, controlStatus]);

  // Mic icon color based on audio socket status (dimmed when control not connected)
  const micColor = micDisabled
    ? '#555'
    : audioSocket.status === 'connected'
      ? '#34d399'
      : audioSocket.status === 'connecting'
        ? '#f59e0b'
        : '#b9b9ba';

  // Spinning animation for connecting state
  const spinValue = useSharedValue(0);
  useEffect(() => {
    if (audioSocket.status === 'connecting') {
      spinValue.value = 0;
      spinValue.value = withRepeat(withTiming(1, { duration: 1000 }), -1);
    } else {
      cancelAnimation(spinValue);
      spinValue.value = 0;
    }
  }, [audioSocket.status, spinValue]);

  const micAnimatedStyle = useAnimatedStyle(() => ({
    transform: [{ rotate: `${spinValue.value * 360}deg` }],
  }));

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed && attachments.length === 0) return;
    onSend(trimmed, attachments);
    setText('');
    setAttachments([]);
  };

  const handleMicPress = useCallback(async () => {
    // Block until control socket is established
    if (controlStatus !== 'connected') return;

    // If audio socket isn't connected, initiate connection first
    if (audioSocket.status !== 'connected') {
      audioSocket.connect();
      return;
    }

    const { status } = await ExpoAudioStreamModule.requestPermissionsAsync();
    if (status !== 'granted') return;

    // Send audio_start frame
    audioSocket.sendJSON({
      type: 'audio_start',
      sampleRate: recordingConfig.sampleRate,
      encoding: recordingConfig.encoding,
      channels: recordingConfig.channels,
    });

    await startRecording(recordingConfig);
  }, [startRecording, audioSocket, controlStatus, recordingConfig]);

  const handleCancelRecording = useCallback(async () => {
    await stopRecording();
    resetBars();
    audioSocket.sendJSON({ type: 'audio_end' });
    // discard — don't fire onAudioRecorded
  }, [stopRecording, audioSocket, resetBars]);

  const handleSendRecording = useCallback(async () => {
    const result = await stopRecording();
    resetBars();
    audioSocket.sendJSON({ type: 'audio_end' });
    onAudioRecorded?.(result);
  }, [stopRecording, onAudioRecorded, audioSocket, resetBars]);

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
          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', height: 64, gap: 6, marginBottom: 12 }}>
            {bars.map((sv, i) => (
              <VoiceBar key={i} sv={sv} />
            ))}
          </View>

          <View className="flex-row items-center">
            <Pressable onPress={handleCancelRecording} style={pressStyle} className="size-11 rounded-xl bg-bg-button items-center justify-center">
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

            <Pressable onPress={handleSendRecording} style={pressStyle} className="size-11 rounded-xl bg-accent items-center justify-center">
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
              <View key={i} className="relative rounded-xl overflow-hidden w-25 h-25">
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
          className="text-[15px] text-text-primary min-h-7 mb-2.5"
          placeholder="Ask anything..."
          placeholderTextColor="#b9b9ba"
          value={text}
          onChangeText={setText}
          onSubmitEditing={handleSend}
          multiline
        />

        <View className="flex-row items-center">
          <Pressable onPress={pickImage} style={pressStyle} className="size-8.5 rounded-lg bg-bg-button items-center justify-center">
            <IconSymbol name="plus" size={20} color="#e5e5e5" />
          </Pressable>
          <View className="ml-2">
            <ModeSelector mode={mode} onModeChange={setMode} />
          </View>
          <View className="flex-1" />
          <Pressable
            onPress={handleMicPress}
            disabled={micDisabled}
            android_ripple={null}
            className="size-9 items-center justify-center"
            style={{ opacity: micDisabled ? 0.4 : 1 }}
          >
            <Animated.View style={micAnimatedStyle}>
              <IconSymbol name="mic.fill" size={20} color={micColor} />
            </Animated.View>
          </Pressable>
          <Pressable onPress={handleSend} style={pressStyle} className="size-9 rounded-input bg-accent items-center justify-center ml-1.5">
            <IconSymbol name="arrow.up" size={20} color="#fff" />
          </Pressable>
        </View>
      </View>
    </View>
  );
}
