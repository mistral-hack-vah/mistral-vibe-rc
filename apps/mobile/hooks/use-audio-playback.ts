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
    if (stoppedRef.current) {
      console.log('[AudioPlayback] playBuffered skipped — stopped');
      return;
    }
    if (chunksRef.current.length === 0) {
      console.log('[AudioPlayback] playBuffered skipped — no chunks');
      return;
    }

    const toPlay = chunksRef.current.splice(0); // drain entire buffer
    const totalB64Len = toPlay.reduce((s, c) => s + c.length, 0);
    console.log(`[AudioPlayback] playBuffered: ${toPlay.length} chunks, totalB64=${totalB64Len}`);

    // Decode each chunk separately — they have independent base64 padding
    const decoded = toPlay.map((chunk) => {
      const raw = atob(chunk);
      const arr = new Uint8Array(raw.length);
      for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
      return arr;
    });
    const totalLen = decoded.reduce((sum, b) => sum + b.length, 0);
    const bytes = new Uint8Array(totalLen);
    let off = 0;
    for (const b of decoded) {
      bytes.set(b, off);
      off += b.length;
    }

    const filename = `tts_${Date.now()}.mp3`;
    const file = new File(Paths.cache, filename);
    console.log(`[AudioPlayback] writing ${bytes.length} bytes to ${filename}`);
    try {
      file.write(bytes);
      // Clean up previous file
      try { currentFileRef.current?.delete(); } catch {}
      currentFileRef.current = file;
      playStateRef.current = 'starting';
      console.log(`[AudioPlayback] player.replace({ uri: ${file.uri} })`);
      player.replace({ uri: file.uri });
      console.log('[AudioPlayback] player.play()');
      player.play();
    } catch (e) {
      console.warn('[AudioPlayback] Error writing/playing:', e);
      try { file.delete(); } catch {}
      playStateRef.current = 'idle';
    }
  }, [player]);

  // Detect playback completion via status updates
  useEffect(() => {
    console.log(`[AudioPlayback] status.playing=${status.playing}  playState=${playStateRef.current}  buffered=${chunksRef.current.length}`);
    if (playStateRef.current === 'starting' && status.playing) {
      // Player confirmed started
      console.log('[AudioPlayback] → transition: starting → playing');
      playStateRef.current = 'playing';
    } else if (playStateRef.current === 'playing' && !status.playing) {
      // Playback finished — play any buffered chunks that arrived while playing
      console.log(`[AudioPlayback] → transition: playing → idle  (buffered=${chunksRef.current.length})`);
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
        const b64 = event.data.audio as string;
        chunksRef.current.push(b64);
        console.log(`[AudioPlayback] feedEvent audio_delta: b64len=${b64.length}  totalChunks=${chunksRef.current.length}  playState=${playStateRef.current}`);
        // Start playing immediately if idle
        if (playStateRef.current === 'idle') {
          console.log('[AudioPlayback] feedEvent → triggering playBuffered (was idle)');
          playBuffered();
        }
      } else if (event.event === 'tts_done') {
        console.log(`[AudioPlayback] feedEvent tts_done: playState=${playStateRef.current}  buffered=${chunksRef.current.length}`);
        // Final drain — play anything left that arrived during the last playback
        if (playStateRef.current === 'idle' && chunksRef.current.length > 0) {
          playBuffered();
        }
      }
    },
    [playBuffered]
  );

  const stop = useCallback(() => {
    console.log('[AudioPlayback] stop() called — clearing all state');
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
