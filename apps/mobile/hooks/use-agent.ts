/**
 * useAgent — central orchestrator hook.
 *
 * Unifies WebSocket events and REST SSE streaming into a single
 * message list + agent status. This is the main interface for the
 * chat screen.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useAudioSocket, type ServerEvent } from './use-audio-socket';
import { useAudioPlayback } from './use-audio-playback';
import * as api from './api-client';
import type { RepoConfig } from './api-client';
import type { Message, Attachment } from '@/components/chat/types';

export type AgentStatus = 'idle' | 'recording' | 'transcribing' | 'responding';

export function useAgent() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [status, setStatus] = useState<AgentStatus>('idle');
  const [mode, setMode] = useState<'plan' | 'build'>('plan');

  // Repository state
  const [repos, setRepos] = useState<RepoConfig[]>([]);
  const [activeRepo, setActiveRepo] = useState<RepoConfig | null>(null);

  const audioSocket = useAudioSocket();
  const { feedEvent: feedAudio, stop: stopAudio } = useAudioPlayback();
  const sessionIdRef = useRef<string | null>(null);

  // Load repos on mount
  useEffect(() => {
    api.getRepos().then((loadedRepos) => {
      setRepos(loadedRepos);
      const defaultRepo = loadedRepos.find((r) => r.is_default) ?? loadedRepos[0];
      if (defaultRepo) {
        setActiveRepo(defaultRepo);
      }
    }).catch((e) => {
      console.warn('[useAgent] Failed to load repos:', e);
    });
  }, []);

  // -----------------------------------------------------------------------
  // WS event handler
  // -----------------------------------------------------------------------
  const handleEvent = useCallback(
    (event: ServerEvent) => {
      // Forward audio events to playback
      feedAudio(event);

      switch (event.event) {
        case 'session':
          sessionIdRef.current = event.data.session_id as string;
          break;

        case 'recording':
          if (event.data.status === 'started') {
            setStatus('recording');
            console.log('[useAgent] recording started');
          } else if (event.data.status === 'stopped') {
            setStatus('transcribing');
            console.log('[useAgent] recording stopped, transcribing...');
          } else if (event.data.status === 'cancelled') {
            setStatus('idle');
            console.log('[useAgent] recording cancelled');
          }
          break;

        case 'transcribing':
          setStatus('transcribing');
          console.log('[useAgent] transcribing...');
          break;

        case 'transcript': {
          const text = event.data.text as string;
          console.log('[useAgent] transcript:', text);
          if (text) {
            setMessages((prev) => [
              ...prev,
              {
                type: 'text',
                role: 'user',
                content: text,
                timestamp: Date.now(),
              },
            ]);
          }
          break;
        }

        case 'agent_start':
          setStatus('responding');
          // Append empty streaming assistant message
          setMessages((prev) => [
            ...prev,
            {
              type: 'text',
              role: 'assistant',
              content: '',
              isStreaming: true,
              timestamp: Date.now(),
            },
          ]);
          break;

        case 'agent_delta': {
          const delta = event.data.text as string;
          setMessages((prev) => {
            const updated = [...prev];
            // Find last assistant message that is streaming
            for (let i = updated.length - 1; i >= 0; i--) {
              const m = updated[i];
              if (m.type === 'text' && m.role === 'assistant' && m.isStreaming) {
                updated[i] = { ...m, content: m.content + delta };
                break;
              }
            }
            return updated;
          });
          break;
        }

        case 'agent_done': {
          const fullText = event.data.text as string;
          setStatus('idle');
          setMessages((prev) => {
            const updated = [...prev];
            for (let i = updated.length - 1; i >= 0; i--) {
              const m = updated[i];
              if (m.type === 'text' && m.role === 'assistant' && m.isStreaming) {
                updated[i] = {
                  ...m,
                  content: fullText || m.content,
                  isStreaming: false,
                };
                break;
              }
            }
            return updated;
          });
          break;
        }

        case 'history': {
          const turns = event.data.turns as Array<{
            role: string;
            content: string;
          }>;
          if (turns && turns.length > 0) {
            const hydrated: Message[] = turns.map((t) => ({
              type: 'text' as const,
              role: t.role as 'user' | 'assistant',
              content: t.content,
            }));
            setMessages(hydrated);
          }
          break;
        }

        case 'error': {
          const errorMsg = event.data.message as string;
          setStatus('idle');
          setMessages((prev) => [
            ...prev,
            { type: 'notification', content: errorMsg },
          ]);
          break;
        }

        case 'state':
          if (event.data.status === 'interrupted') {
            setStatus('idle');
            stopAudio();
            // Finalize any streaming message
            setMessages((prev) =>
              prev.map((m) =>
                m.type === 'text' && m.isStreaming
                  ? { ...m, isStreaming: false }
                  : m
              )
            );
          }
          break;
      }
    },
    [feedAudio, stopAudio]
  );

  // Subscribe to WS events
  useEffect(() => {
    return audioSocket.onEvent(handleEvent);
  }, [audioSocket, handleEvent]);

  // -----------------------------------------------------------------------
  // Text message flow (REST SSE)
  // -----------------------------------------------------------------------
  const sendTextMessage = useCallback(
    async (text: string, attachments: Attachment[] = []) => {
      const sessionId = sessionIdRef.current;
      if (!sessionId) {
        console.warn('[useAgent] No session — cannot send text message');
        return;
      }

      // Optimistic user message
      const userMsg: Message = {
        type: 'text',
        role: 'user',
        content: text,
        attachments: attachments.length > 0 ? attachments : undefined,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, userMsg]);

      // Upload images if any
      let imageUris: string[] = [];
      if (attachments.length > 0) {
        try {
          imageUris = await Promise.all(
            attachments
              .filter((a) => a.type === 'image')
              .map((a) => api.uploadFile(a.uri, a.name))
          );
        } catch (e) {
          console.warn('[useAgent] Image upload failed:', e);
        }
      }

      // Stream SSE response (pass active repo's path as workdir)
      try {
        for await (const event of api.sendMessage(
          sessionId,
          text,
          imageUris,
          activeRepo?.path
        )) {
          handleEvent(event);
        }
      } catch (e) {
        setStatus('idle');
        setMessages((prev) => [
          ...prev,
          {
            type: 'notification',
            content: `Error: ${e instanceof Error ? e.message : String(e)}`,
          },
        ]);
      }
    },
    [handleEvent, activeRepo]
  );

  // -----------------------------------------------------------------------
  // Interrupt
  // -----------------------------------------------------------------------
  const interruptAgent = useCallback(async () => {
    const sessionId = sessionIdRef.current;
    if (!sessionId) return;

    // Send interrupt via both WS and REST for redundancy
    try {
      audioSocket.sendInterrupt();
    } catch {
      // socket may not be connected
    }
    try {
      await api.interrupt(sessionId);
    } catch {
      // REST interrupt is best-effort
    }
    stopAudio();
  }, [audioSocket, stopAudio]);

  // -----------------------------------------------------------------------
  // Connect
  // -----------------------------------------------------------------------
  const connect = useCallback(
    (sessionId?: string) => {
      audioSocket.connect(sessionId);
    },
    [audioSocket]
  );

  // -----------------------------------------------------------------------
  // Repository Management
  // -----------------------------------------------------------------------
  const selectRepo = useCallback(
    (repoId: string) => {
      const repo = repos.find((r) => r.id === repoId);
      if (repo) {
        setActiveRepo(repo);
        // Also notify the WebSocket about the repo change
        try {
          audioSocket.sendJSON({ type: 'set_repo', repo_id: repoId });
        } catch {
          // Socket may not be connected
        }
      }
    },
    [repos, audioSocket]
  );

  const addRepo = useCallback(async (path: string, name?: string) => {
    const newRepo = await api.addRepo(path, name);
    setRepos((prev) => [...prev, newRepo]);
    if (newRepo.is_default) {
      setActiveRepo(newRepo);
    }
    return newRepo;
  }, []);

  const removeRepo = useCallback(
    async (repoId: string) => {
      await api.removeRepo(repoId);
      setRepos((prev) => prev.filter((r) => r.id !== repoId));
      if (activeRepo?.id === repoId) {
        // Select the first remaining repo
        setActiveRepo((prev) => {
          const remaining = repos.filter((r) => r.id !== repoId);
          return remaining[0] ?? null;
        });
      }
    },
    [activeRepo, repos]
  );

  const refreshRepos = useCallback(async () => {
    const loadedRepos = await api.getRepos();
    setRepos(loadedRepos);
    // Update active repo if it still exists
    if (activeRepo) {
      const updated = loadedRepos.find((r) => r.id === activeRepo.id);
      if (updated) {
        setActiveRepo(updated);
      } else if (loadedRepos.length > 0) {
        setActiveRepo(loadedRepos.find((r) => r.is_default) ?? loadedRepos[0]);
      } else {
        setActiveRepo(null);
      }
    }
  }, [activeRepo]);

  return {
    messages,
    status,
    sessionId: sessionIdRef.current,
    socketStatus: audioSocket.status,
    mode,
    setMode,
    sendTextMessage,
    interrupt: interruptAgent,
    connect,
    audioSocket,
    // Repository management
    repos,
    activeRepo,
    selectRepo,
    addRepo,
    removeRepo,
    refreshRepos,
  };
}
