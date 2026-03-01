/**
 * Audio playback hook — decodes base64 audio_delta chunks from the server
 * and plays them sequentially using expo-audio.
 */

import { useCallback, useEffect, useRef } from 'react';
import { useAudioPlayer } from 'expo-audio';
import { File, Paths } from 'expo-file-system';
import type { ServerEvent } from './use-audio-socket';

/**
 * Hook that subscribes to audio_delta events and plays them.
 *
 * Usage:
 * ```
 * const { feedEvent, stop } = useAudioPlayback();
 * audioSocket.onEvent(feedEvent);
 * ```
 */
export function useAudioPlayback() {
  const player = useAudioPlayer(null);
  const queueRef = useRef<string[]>([]);
  const playingRef = useRef(false);
  const stoppedRef = useRef(false);

  const playNext = useCallback(async () => {
    if (playingRef.current || stoppedRef.current) return;
    const b64 = queueRef.current.shift();
    if (!b64) return;

    playingRef.current = true;
    const file = new File(Paths.cache, `tts_${Date.now()}.mp3`);
    try {
      // Decode base64 to bytes and write to temp file
      const raw = atob(b64);
      const bytes = new Uint8Array(raw.length);
      for (let i = 0; i < raw.length; i++) {
        bytes[i] = raw.charCodeAt(i);
      }
      file.write(bytes);

      player.replace({ uri: file.uri });
      player.play();

      // Wait for playback to finish
      await new Promise<void>((resolve) => {
        const sub = player.addListener('playbackStatusUpdate', (status) => {
          if ('didJustFinish' in status && status.didJustFinish) {
            sub.remove();
            resolve();
          }
        });
      });
    } catch (e) {
      console.warn('[AudioPlayback] Error:', e);
    } finally {
      // Clean up temp file
      try {
        file.delete();
      } catch {}
      playingRef.current = false;
      // Play next chunk in queue
      if (queueRef.current.length > 0 && !stoppedRef.current) {
        playNext();
      }
    }
  }, [player]);

  const feedEvent = useCallback(
    (event: ServerEvent) => {
      if (event.event === 'audio_delta' && event.data?.audio) {
        stoppedRef.current = false;
        queueRef.current.push(event.data.audio as string);
        if (!playingRef.current) {
          playNext();
        }
      }
    },
    [playNext]
  );

  const stop = useCallback(() => {
    stoppedRef.current = true;
    queueRef.current = [];
    player.pause();
  }, [player]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stoppedRef.current = true;
      queueRef.current = [];
    };
  }, []);

  return { feedEvent, stop };
}
