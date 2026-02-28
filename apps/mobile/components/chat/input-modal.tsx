import { useState, useCallback, useEffect, useRef } from 'react';
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
import { AudioVisualizer } from '@siteed/expo-audio-ui';
import { useAudioSocket } from '@/hooks/use-audio-socket';
import { useControlSocket } from '@/hooks/use-control-socket';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withRepeat,
  withTiming,
  cancelAnimation,
} from 'react-native-reanimated';

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

const RECORDING_CONFIG: RecordingConfig = {
  interval: 500,
  enableProcessing: true,
  sampleRate: 44100,
  channels: 1,
  encoding: 'pcm_16bit',
  output: {
    primary: { enabled: true },
    compressed: { enabled: false, format: 'aac', bitrate: 128000 },
  },
  autoResumeAfterInterruption: false,
  bufferDurationSeconds: 0.1,
};

export function InputModal({ onSend, onAudioRecorded }: InputModalProps) {
  const [text, setText] = useState('');
  const [mode, setMode] = useState<'plan' | 'build'>('plan');
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [autosend, setAutosend] = useState(true);

  const {
    startRecording,
    stopRecording,
    isRecording,
    analysisData,
    durationMs,
  } = useAudioRecorder();

  const { status: controlStatus } = useControlSocket();
  const audioSocket = useAudioSocket();
  const micDisabled = controlStatus !== 'connected';

  // Auto-connect audio socket as soon as control is established
  useEffect(() => {
    if (controlStatus === 'connected') {
      audioSocket.connect();
    }
  }, [controlStatus]);

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
      sampleRate: RECORDING_CONFIG.sampleRate,
      encoding: RECORDING_CONFIG.encoding,
      channels: RECORDING_CONFIG.channels,
    });

    await startRecording({
      ...RECORDING_CONFIG,
      onAudioStream: async (evt) => {
        if (!evt.data) return;
        let buffer: ArrayBuffer;
        if (typeof evt.data !== 'string') {
          // Web: convert Float32Array to 16-bit PCM
          const pcm = new Int16Array(evt.data.length);
          for (let i = 0; i < evt.data.length; i++) {
            const s = Math.max(-1, Math.min(1, evt.data[i]));
            pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
          }
          buffer = pcm.buffer;
        } else {
          // Native: base64-encoded PCM string
          const bin = atob(evt.data);
          const bytes = new Uint8Array(bin.length);
          for (let i = 0; i < bin.length; i++) {
            bytes[i] = bin.charCodeAt(i);
          }
          buffer = bytes.buffer;
        }
        // Skip tiny metadata/header chunks — real audio is ≥1000 bytes
        if (buffer.byteLength < 1000) return;
        console.log(`[mic] chunk ${buffer.byteLength} bytes`);
        audioSocket.sendBinary(buffer);
      },
    });
  }, [startRecording, audioSocket, controlStatus]);

  const handleCancelRecording = useCallback(async () => {
    await stopRecording();
    audioSocket.sendJSON({ type: 'audio_end' });
    // discard — don't fire onAudioRecorded
  }, [stopRecording, audioSocket]);

  const handleSendRecording = useCallback(async () => {
    const result = await stopRecording();
    audioSocket.sendJSON({ type: 'audio_end' });
    onAudioRecorded?.(result);
  }, [stopRecording, onAudioRecorded, audioSocket]);

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

  const formatDuration = (ms: number) => {
    const secs = Math.floor(ms / 1000);
    const mins = Math.floor(secs / 60);
    const remaining = secs % 60;
    return `${mins}:${remaining.toString().padStart(2, '0')}`;
  };

  // ─── Recording UI ───
  if (isRecording) {
    return (
      <View className="px-4 pb-2">
        <View className="bg-bg-modal border border-border-soft rounded-2xl px-3.5 pt-4 pb-3">
          {/* Waveform visualizer */}
          <View className="items-center mb-3">
            {analysisData ? (
              <AudioVisualizer
                audioData={analysisData}
                canvasHeight={64}
                candleWidth={6}
                candleSpace={3}
                mode="live"
                showDottedLine={false}
                showRuler={false}
                showYAxis={false}
                showNavigation={false}
                showSelectedCandle={false}
                showReferenceLine={false}
                amplitudeScaling="humanVoice"
                theme={{
                  container: {},
                  navigationContainer: {},
                  canvasContainer: {},
                  referenceLine: {},
                  text: {},
                  button: {},
                  buttonText: {},
                  dottedLineColor: 'transparent',
                  yAxis: { tickColor: 'transparent', labelColor: 'transparent' },
                  timeRuler: {
                    tickColor: 'transparent',
                    labelColor: 'transparent',
                  },
                  candle: {
                    activeAudioColor: '#7cd659',
                    activeSpeechColor: '#4ade80',
                    offcanvasColor: '#3a5a2e',
                  },
                }}
              />
            ) : (
              <View className="h-[64px] justify-center items-center">
                <View className="flex-row items-center gap-1.5">
                  {Array.from({ length: 11 }).map((_, i) => {
                    const center = 5;
                    const dist = Math.abs(i - center);
                    const size = Math.max(4, 12 - dist * 2);
                    return (
                      <View
                        key={i}
                        style={{
                          width: size,
                          height: size,
                          borderRadius: size / 2,
                          backgroundColor:
                            dist === 0 ? '#4ade80' : '#7cd659',
                          opacity: 1 - dist * 0.08,
                        }}
                      />
                    );
                  })}
                </View>
              </View>
            )}
          </View>

          {/* Duration */}
          <Text className="text-center text-text-secondary text-xs mb-3">
            {formatDuration(durationMs)}
          </Text>

          {/* Bottom row: cancel, autosend, send */}
          <View className="flex-row items-center">
            {/* Cancel button */}
            <Pressable
              onPress={handleCancelRecording}
              style={pressStyle}
              className="size-[44px] rounded-xl bg-bg-button items-center justify-center"
            >
              <IconSymbol name="xmark" size={18} color="#b9b9ba" />
            </Pressable>

            {/* Autosend toggle */}
            <View className="flex-1 flex-row items-center justify-center">
              <Text className="text-text-primary text-[15px] font-medium mr-2">
                Autosend
              </Text>
              <Pressable
                onPress={() => setAutosend((v) => !v)}
                style={{
                  backgroundColor: autosend
                    ? 'rgba(230, 93, 45, 0.25)'
                    : 'rgba(255,255,255,0.1)',
                  paddingHorizontal: 8,
                  paddingVertical: 3,
                  borderRadius: 6,
                }}
              >
                <Text
                  style={{
                    color: autosend ? '#e65d2d' : '#b9b9ba',
                    fontSize: 13,
                    fontWeight: '700',
                  }}
                >
                  {autosend ? 'ON' : 'OFF'}
                </Text>
              </Pressable>
            </View>

            {/* Send button */}
            <Pressable
              onPress={handleSendRecording}
              style={pressStyle}
              className="size-[44px] rounded-xl bg-accent items-center justify-center"
            >
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
