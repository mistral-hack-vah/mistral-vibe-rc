/**
 * Audio playback hook — low-latency TTS playback.
 *
 * Strategy:
 *  1. Play the first audio_delta chunk immediately (low latency).
 *  2. While that plays, buffer all incoming chunks.
 *  3. When playback finishes, concatenate remaining buffered chunks
 *     into one file and play — no per-chunk gaps.
 *  4. tts_done triggers a final drain of any leftover chunks.
 */

import { useAudioPlayer, useAudioPlayerStatus } from 'expo-audio';
import { File, Paths } from 'expo-file-system';
import { useCallback, useEffect, useRef } from 'react';
import type { ServerEvent } from './use-audio-socket';

type PlayState = 'idle' | 'starting' | 'playing';

export function useAudioPlayback() {
  const player = useAudioPlayer(null);
  const status = useAudioPlayerStatus(player);

  const chunksRef = useRef<string[]>([]);
  const playStateRef = useRef<PlayState>('idle');
  const currentFileRef = useRef<File | null>(null);
  const stoppedRef = useRef(false);

  const playBuffered = useCallback(() => {
    if (stoppedRef.current || chunksRef.current.length === 0) return;

    const toPlay = chunksRef.current.splice(0); // drain entire buffer
    const raw = atob(toPlay.join(''));
    const bytes = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);

    const file = new File(Paths.cache, `tts_${Date.now()}.mp3`);
    try {
      file.write(bytes);
      // Clean up previous file
      try { currentFileRef.current?.delete(); } catch {}
      currentFileRef.current = file;
      playStateRef.current = 'starting';
      player.replace({ uri: file.uri });
      player.play();
    } catch (e) {
      console.warn('[AudioPlayback] Error:', e);
      try { file.delete(); } catch {}
      playStateRef.current = 'idle';
    }
  }, [player]);

  // Detect playback completion via status updates
  useEffect(() => {
    if (playStateRef.current === 'starting' && status.playing) {
      // Player confirmed started
      playStateRef.current = 'playing';
    } else if (playStateRef.current === 'playing' && !status.playing) {
      // Playback finished — play any buffered chunks that arrived while playing
      playStateRef.current = 'idle';
      try { currentFileRef.current?.delete(); } catch {}
      currentFileRef.current = null;
      if (chunksRef.current.length > 0) {
        playBuffered();
      }
    }
  }, [status.playing, playBuffered]);

  const feedEvent = useCallback(
    (event: ServerEvent) => {
      if (event.event === 'audio_delta' && event.data?.audio) {
        stoppedRef.current = false;
        chunksRef.current.push(event.data.audio as string);
        // Start playing immediately if idle
        if (playStateRef.current === 'idle') {
          playBuffered();
        }
      } else if (event.event === 'tts_done') {
        // Final drain — play anything left that arrived during the last playback
        if (playStateRef.current === 'idle' && chunksRef.current.length > 0) {
          playBuffered();
        }
      }
    },
    [playBuffered]
  );

  const stop = useCallback(() => {
    stoppedRef.current = true;
    chunksRef.current = [];
    playStateRef.current = 'idle';
    player.pause();
    try { currentFileRef.current?.delete(); } catch {}
    currentFileRef.current = null;
  }, [player]);

  useEffect(() => {
    return () => {
      stoppedRef.current = true;
      chunksRef.current = [];
    };
  }, []);

  return { feedEvent, stop };
}
