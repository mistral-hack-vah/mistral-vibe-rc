/**
 * REST API client for the Python backend.
 *
 * Handles session management, message sending (with SSE streaming),
 * file upload, and interrupt.
 */

import { getApiBaseUrl, authHeaders } from './config';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export type ServerEvent = {
  event: string;
  data: Record<string, unknown>;
};

type SessionResponse = {
  session_id: string;
  created_at: number;
};

type HistoryResponse = {
  turns: Array<{ role: string; content: string }>;
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function apiUrl(path: string): string {
  return `${getApiBaseUrl()}${path}`;
}

function headers(extra?: Record<string, string>): Record<string, string> {
  return {
    'Content-Type': 'application/json',
    ...authHeaders(),
    ...extra,
  };
}

// ---------------------------------------------------------------------------
// REST Methods
// ---------------------------------------------------------------------------

/** Create or recover a session. */
export async function createSession(
  sessionId?: string
): Promise<SessionResponse> {
  const res = await fetch(apiUrl('/api/session'), {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ session_id: sessionId ?? null }),
  });
  if (!res.ok) throw new Error(`createSession failed: ${res.status}`);
  return res.json();
}

/** Get conversation history for a session. */
export async function getHistory(
  sessionId: string
): Promise<HistoryResponse> {
  const res = await fetch(apiUrl(`/api/session/${sessionId}/history`), {
    headers: headers(),
  });
  if (!res.ok) throw new Error(`getHistory failed: ${res.status}`);
  return res.json();
}

/** Interrupt the current agent stream. */
export async function interrupt(sessionId: string): Promise<void> {
  const res = await fetch(apiUrl('/api/interrupt'), {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ session_id: sessionId }),
  });
  if (!res.ok) throw new Error(`interrupt failed: ${res.status}`);
}

/** Upload a file and return its server URL. */
export async function uploadFile(
  uri: string,
  name: string
): Promise<string> {
  const formData = new FormData();
  formData.append('file', {
    uri,
    name,
    type: 'image/jpeg',
  } as unknown as Blob);

  const res = await fetch(apiUrl('/api/upload'), {
    method: 'POST',
    headers: authHeaders(),
    body: formData,
  });
  if (!res.ok) throw new Error(`uploadFile failed: ${res.status}`);
  const json = await res.json();
  return `${getApiBaseUrl()}${json.url}`;
}

/**
 * Send a text message and stream the response via SSE.
 *
 * Yields parsed server events: agent_start, agent_delta, agent_done, error, audio_delta.
 */
export async function* sendMessage(
  sessionId: string,
  text: string,
  imageUris: string[] = []
): AsyncGenerator<ServerEvent> {
  const res = await fetch(apiUrl('/api/message'), {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({
      session_id: sessionId,
      text,
      image_uris: imageUris,
    }),
  });

  if (!res.ok) throw new Error(`sendMessage failed: ${res.status}`);
  if (!res.body) throw new Error('No response body');

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';

    let currentEvent = '';
    for (const line of lines) {
      if (line.startsWith('event:')) {
        currentEvent = line.slice(6).trim();
      } else if (line.startsWith('data:')) {
        const dataStr = line.slice(5).trim();
        if (currentEvent && dataStr) {
          try {
            const data = JSON.parse(dataStr);
            yield { event: currentEvent, data };
          } catch {
            // skip malformed JSON
          }
          currentEvent = '';
        }
      }
    }
  }
}
