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
import type { Message, Attachment } from '@/components/chat/types';
import type { PermissionType } from './use-permissions';

type PermissionChecker = (
  type: PermissionType,
  description: string,
  detail?: string
) => Promise<boolean>;

export type AgentStatus = 'idle' | 'recording' | 'transcribing' | 'responding' | 'speaking';

type UseAgentOptions = {
  requestPermission?: PermissionChecker;
};

export function useAgent(options: UseAgentOptions = {}) {
  const { requestPermission } = options;
  const [messages, setMessages] = useState<Message[]>([]);
  const [status, setStatus] = useState<AgentStatus>('idle');
  const [mode, setMode] = useState<'plan' | 'build'>('plan');

  const audioSocket = useAudioSocket();
  const { feedEvent: feedAudio, stop: stopAudio } = useAudioPlayback();
  const sessionIdRef = useRef<string | null>(null);

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
            console.log('[useAgent] recording stopped');
          } else if (event.data.status === 'cancelled') {
            setStatus('idle');
            // Remove any in-progress streaming user message
            setMessages((prev) =>
              prev.filter(
                (m) => !(m.type === 'text' && m.role === 'user' && m.isStreaming)
              )
            );
            console.log('[useAgent] recording cancelled');
          }
          break;

        case 'transcribing':
          setStatus('transcribing');
          break;

        case 'transcript_delta': {
          const deltaText = event.data.text as string;
          if (!deltaText) break;
          setMessages((prev) => {
            // Find existing streaming user message to append to
            for (let i = prev.length - 1; i >= 0; i--) {
              const m = prev[i];
              if (m.type === 'text' && m.role === 'user' && m.isStreaming) {
                const updated = [...prev];
                updated[i] = { ...m, content: m.content + deltaText };
                return updated;
              }
            }
            // Create a new streaming user message
            return [
              ...prev,
              {
                type: 'text' as const,
                role: 'user' as const,
                content: deltaText,
                isStreaming: true,
                timestamp: Date.now(),
              },
            ];
          });
          break;
        }

        case 'transcript': {
          const text = event.data.text as string;
          console.log('[useAgent] transcript:', text);
          setMessages((prev) => {
            // Finalize the streaming user message
            for (let i = prev.length - 1; i >= 0; i--) {
              const m = prev[i];
              if (m.type === 'text' && m.role === 'user' && m.isStreaming) {
                const updated = [...prev];
                if (text) {
                  updated[i] = { ...m, content: text, isStreaming: false };
                } else {
                  // Empty transcript — remove the streaming message
                  updated.splice(i, 1);
                }
                return updated;
              }
            }
            // No streaming message found — add final transcript directly
            if (text) {
              return [
                ...prev,
                {
                  type: 'text' as const,
                  role: 'user' as const,
                  content: text,
                  timestamp: Date.now(),
                },
              ];
            }
            return prev;
          });
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
          // Transition to 'speaking' — tts_done will set 'idle'
          setStatus('speaking');
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

        case 'tts_done':
          setStatus('idle');
          break;
        case 'edit': {
          const { filePath, diff } = event.data as { filePath: string; diff: string };
          if (filePath && diff) {
            // Show pending edit, then request permission
            const editMsg: Message = { type: 'edit', filePath, diff, status: 'pending' };
            setMessages((prev) => [...prev, editMsg]);

            // Request permission asynchronously
            if (requestPermission) {
              requestPermission('edit', 'Edit file', filePath).then((granted) => {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.type === 'edit' && m.filePath === filePath && m.status === 'pending'
                      ? { ...m, status: granted ? 'approved' : 'denied' }
                      : m
                  )
                );
              });
            } else {
              // No permission system, auto-approve
              setMessages((prev) =>
                prev.map((m) =>
                  m.type === 'edit' && m.filePath === filePath && m.status === 'pending'
                    ? { ...m, status: 'approved' }
                    : m
                )
              );
            }
          }
          break;
        }

        case 'read': {
          const { filePath } = event.data as { filePath: string };
          if (filePath) {
            const readMsg: Message = { type: 'read_request', filePath, status: 'pending' };
            setMessages((prev) => [...prev, readMsg]);

            if (requestPermission) {
              requestPermission('read', 'Read file', filePath).then((granted) => {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.type === 'read_request' && m.filePath === filePath && m.status === 'pending'
                      ? { ...m, status: granted ? 'approved' : 'denied' }
                      : m
                  )
                );
              });
            } else {
              setMessages((prev) =>
                prev.map((m) =>
                  m.type === 'read_request' && m.filePath === filePath && m.status === 'pending'
                    ? { ...m, status: 'approved' }
                    : m
                )
              );
            }
          }
          break;
        }

        case 'execute': {
          const { command } = event.data as { command: string };
          if (command) {
            const execMsg: Message = { type: 'execute_request', command, status: 'pending' };
            setMessages((prev) => [...prev, execMsg]);

            if (requestPermission) {
              requestPermission('execute', 'Run command', command).then((granted) => {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.type === 'execute_request' && m.command === command && m.status === 'pending'
                      ? { ...m, status: granted ? 'approved' : 'denied' }
                      : m
                  )
                );
              });
            } else {
              setMessages((prev) =>
                prev.map((m) =>
                  m.type === 'execute_request' && m.command === command && m.status === 'pending'
                    ? { ...m, status: 'approved' }
                    : m
                )
              );
            }
          }
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
    [feedAudio, stopAudio, requestPermission]
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

      // Stream SSE response
      try {
        for await (const event of api.sendMessage(sessionId, text, imageUris)) {
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
    [handleEvent]
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
  };
}
