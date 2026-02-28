# Client-Side Implementation Tasks

> Everything the mobile/web client still needs to become a fully functional remote control.

---

## Architecture Decision: Two WebSocket Channels

```
/ws/control  — JSON text frames (messages, tool calls, notifications, interrupts, permissions)
/ws/audio    — binary frames (PCM chunks up from mic, TTS chunks down from ElevenLabs)
```

**Why two sockets:**
- Audio chunks at 100ms intervals (44.1kHz PCM ≈ 8.8KB/chunk). Base64-encoding inside JSON adds 33% bloat + parse overhead on every frame.
- A dedicated binary WS for audio is cleaner — raw `ArrayBuffer` in both directions, no serialization.
- Audio can be independently connected/disconnected (e.g. text-only mode doesn't need it).
- Interrupt goes over `/ws/control` — the server coordinates stopping both channels.

---

## 0. Codegen Pipeline — Pydantic → Zod

Single source of truth: Pydantic models on the server. Generated Zod schemas on the client for runtime validation.

```
apps/server/src/models/ws_messages.py       ← source of truth (Pydantic discriminated unions)
    ↓  model_json_schema()
shared/schemas/                             ← intermediate JSON Schema files
    ControlClientMessage.schema.json
    ControlServerMessage.schema.json
    AudioClientMessage.schema.json
    AudioServerMessage.schema.json
    ↓  json-schema-to-zod
apps/mobile/types/ws-messages.zod.ts        ← generated Zod schemas (don't hand-edit)
apps/mobile/types/ws-messages.ts            ← generated inferred TS types (z.infer<>)
```

### Tasks

- [ ] Write Pydantic models for all control channel messages (client→server and server→client) as discriminated unions on `type` field
- [ ] Write Pydantic models for audio channel messages (minimal — mostly metadata, the actual audio is binary frames)
- [ ] Create `scripts/gen_schemas.py` that calls `.model_json_schema()` on each root model and writes to `shared/schemas/`
- [ ] Add `json-schema-to-zod` as a devDependency in the mobile app
- [ ] Create `scripts/gen_zod.sh` that runs `json-schema-to-zod` on each schema file → outputs `.zod.ts` files
- [ ] Create a wrapper `scripts/gen_types.sh` that runs the Python step then the Zod step
- [ ] Add `"gen:types": "bash scripts/gen_types.sh"` to root `package.json`
- [ ] Add a generated `ws-messages.ts` that re-exports `z.infer<typeof ...>` types for easy import
- [ ] Validate incoming WS frames on the client with the generated Zod schemas before dispatching

---

## 1. Wire Protocol — Message Definitions

All messages defined as Pydantic models (see §0). The shapes below are the spec.

### Control Channel — Client → Server

- [ ] `{ type: "init" }` — handshake after connect
- [ ] `{ type: "message", text: string, imageUris: string[], mode: "plan" | "build" }` — user prompt
- [ ] `{ type: "interrupt" }` — stop current agent response
- [ ] `{ type: "mode_change", mode: "plan" | "build" }` — switch agent mode
- [ ] `{ type: "permission_response", requestId: string, allowed: boolean }` — answer permission prompts

### Control Channel — Server → Client

- [ ] `{ type: "session_history", messages: Message[], mode: "plan" | "build" }` — full state on connect
- [ ] `{ type: "text_delta", content: string }` — streaming token from agent
- [ ] `{ type: "text_done" }` — agent finished text response
- [ ] `{ type: "tool_call_start", id: string, name: string, args: string }` — tool invocation began
- [ ] `{ type: "tool_call_result", id: string, name: string, result: string }` — tool finished
- [ ] `{ type: "notification", content: string }` — agent status/notification
- [ ] `{ type: "permission_request", requestId: string, description: string }` — agent needs approval
- [ ] `{ type: "error", message: string }` — server error

### Audio Channel — Client → Server

- [ ] Binary frames: raw PCM chunks from mic (header-less, format negotiated on control channel)
- [ ] `{ type: "audio_start", sampleRate: number, encoding: string, channels: number }` — one JSON text frame at start of recording to set format
- [ ] `{ type: "audio_end" }` — user stopped speaking (JSON text frame)

### Audio Channel — Server → Client

- [ ] Binary frames: TTS audio chunks from ElevenLabs (mp3 or pcm)
- [ ] `{ type: "audio_start", format: string, sampleRate: number }` — format metadata before first chunk
- [ ] `{ type: "audio_done" }` — TTS finished for this response

---

## 2. WebSocket Hooks — Control & Audio

Split the current `useWebSocket` into two hooks, or one hook managing two connections.

### `useControlSocket`

- [ ] Connect to `/ws/control` with exponential backoff (migrate from current `useWebSocket`)
- [ ] Send `{ type: "init" }` on successful connection (`onopen`)
- [ ] Expose `send(msg: ControlClientMessage)` — JSON serializes and sends text frame
- [ ] `onmessage`: parse JSON, validate with Zod schema, dispatch by `type`
- [ ] Expose `on(type, handler)` / `off(type, handler)` subscription API
- [ ] Handle `{ type: "error" }` from server — surface to UI
- [ ] Queue messages if socket isn't connected yet, flush on reconnect
- [ ] Return `{ status, send, on, off }`

### `useAudioSocket`

- [ ] Connect to `/ws/audio` — only when audio mode is active (lazy connect)
- [ ] Same backoff/reconnect strategy
- [ ] Expose `sendBinary(chunk: ArrayBuffer)` for mic PCM chunks
- [ ] Expose `sendJSON(msg)` for `audio_start` / `audio_end` text frames
- [ ] `onmessage`: route binary frames to audio player, text frames to metadata handler
- [ ] Expose `onAudioChunk(handler)` callback for incoming TTS data
- [ ] `disconnect()` when leaving audio mode
- [ ] Return `{ status, sendBinary, sendJSON, onAudioChunk, connect, disconnect }`

---

## 3. Image Upload (HTTP)

- [ ] Create `uploadImage(uri: string): Promise<string>` utility:
  - Read local file via `expo-file-system`
  - POST as `multipart/form-data` to `POST /api/images`
  - Return server-side URI/path
- [ ] After picking images in `input-modal.tsx`, upload before sending the message
- [ ] Replace local `attachment.uri` with server-returned URI in the outgoing message
- [ ] Show upload progress indicator on image thumbnails
- [ ] Handle upload failures (retry, remove, notify user)

---

## 4. Sending Messages Over Control Socket

Currently `handleSend` in `index.tsx` only appends to local state.

- [ ] On send: upload image attachments first (§3), collect server URIs
- [ ] Send `{ type: "message", text, imageUris, mode }` via control socket
- [ ] Include current `mode` (plan/build) from mode selector
- [ ] Optimistically add user message to local state (already done)
- [ ] Disable send button / show spinner while upload in progress
- [ ] Handle send failures — error toast, allow retry

---

## 5. Streaming Audio to Server (Mic → Voxtral)

The audio recorder captures PCM chunks but doesn't send them.

- [ ] On recording start: connect audio socket if not connected, send `{ type: "audio_start", sampleRate, encoding, channels }` text frame
- [ ] Hook into `onAudioStream` / buffer callback to get real-time PCM chunks
- [ ] Send each chunk as a binary frame via audio socket
- [ ] On recording stop: send `{ type: "audio_end" }` text frame
- [ ] If autosend ON: stream chunks as they arrive
- [ ] If autosend OFF: buffer locally, send as single blob on manual send
- [ ] Consider downsampling to 16kHz if Voxtral expects it (reduces bandwidth ~2.75x)

---

## 6. Receiving & Playing Server Audio (ElevenLabs TTS)

This is the "live conversation" feel.

- [ ] Create `useAudioPlayer` hook:
  - Receive `audio_start` metadata (format, sample rate)
  - Accept incoming binary audio chunks from audio socket
  - Buffer and queue for gapless low-latency playback
  - Use `expo-av` or `expo-audio` playback API
  - Handle `audio_done` → drain buffer, mark playback complete
- [ ] Start playback on first chunk (don't wait for all)
- [ ] Handle format — ElevenLabs likely sends mp3 or pcm; configure decoder accordingly
- [ ] `flush()` method to immediately stop playback and clear queue (for interrupts)
- [ ] Visual indicator while audio is playing (speaker animation, pulsing waveform)
- [ ] Mute/unmute toggle in UI
- [ ] Manage iOS/Android audio session (duck other audio, speaker vs earpiece)

---

## 7. Streaming Text Response — Live Message Updates

Agent text responses arrive token-by-token.

- [ ] On `text_delta`: if no in-progress assistant message, create one with empty content and append to messages; then append `content` to it
- [ ] On `text_done`: mark current assistant message as complete, stop typing indicator
- [ ] Use a ref or mutable state for the in-progress message to batch renders (throttle with `requestAnimationFrame` or 50ms interval)
- [ ] Show typing/streaming indicator while deltas arrive
- [ ] Auto-scroll to bottom as new tokens arrive (partially done via `onContentSizeChange`)

---

## 8. Tool Calls & Notifications — Live Updates

- [ ] On `tool_call_start`: append `ToolCallMessage` with `id`, `name`, `args`, no `result`
- [ ] On `tool_call_result`: find matching tool call by `id`, set its `result`
- [ ] On `notification`: append `AgentNotification` to messages
- [ ] Add "working" spinner on tool call bubbles while result is pending

---

## 9. Session History Hydration

On (re)connect, server sends current session state.

- [ ] On `session_history`: replace local `messages` array with server state
- [ ] Set `mode` from the session history payload
- [ ] Handle reconnection — don't duplicate messages mid-conversation
- [ ] Show loading state while waiting for session history after connect
- [ ] Add message IDs to `Message` type for deduplication

---

## 10. Interrupt System

Manual stop or voice interrupt while agent is responding.

- [ ] Add **stop button** to UI — visible while agent is responding
- [ ] On stop press: send `{ type: "interrupt" }` on control socket
- [ ] On interrupt: flush audio player immediately (`useAudioPlayer.flush()`)
- [ ] On interrupt: stop appending to current streaming text, mark as truncated
- [ ] **Voice interrupt**: if user starts recording while agent is speaking:
  - Auto-send `{ type: "interrupt" }` on control socket
  - Flush audio playback
  - Begin streaming mic audio on audio socket
- [ ] Handle trailing tokens from server after interrupt (ignore gracefully)

---

## 11. Permission Request UI

Agent may request permission for file ops, tool use, etc.

- [ ] On `permission_request`: show modal/banner with description
- [ ] User can approve or deny
- [ ] Send `{ type: "permission_response", requestId, allowed }` on control socket
- [ ] MVP: auto-approve all (configurable in settings)
- [ ] Show permission requests inline in message history as notifications

---

## 12. Mode Selection Sync

Mode selector (plan/build) exists in UI but doesn't talk to server.

- [ ] On mode change: send `{ type: "mode_change", mode }` on control socket
- [ ] Receive mode from `session_history` on connect (persist across reconnects)
- [ ] Visual mode indicator (already done locally)

---

## 13. Global State Management

Everything lives in component-local `useState`. Won't scale.

- [ ] Introduce Zustand store with slices:
  - `messages: Message[]`
  - `controlStatus: ConnectionStatus`
  - `audioStatus: ConnectionStatus`
  - `isAgentResponding: boolean`
  - `isAudioPlaying: boolean`
  - `currentMode: "plan" | "build"`
  - `pendingPermissions: PermissionRequest[]`
- [ ] Move socket instances into the store / a provider so all components can send
- [ ] Persist session ID and mode to `AsyncStorage`
- [ ] Actions: `addMessage`, `updateMessage`, `setMessages`, `setMode`, etc.

---

## 14. Error Handling & Edge Cases

- [ ] Handle control socket disconnect mid-stream (partial text, orphaned tool calls)
- [ ] Handle audio socket disconnect mid-stream (partial playback)
- [ ] Show reconnection banner — "Reconnecting..." with status
- [ ] Display server errors in chat as notifications
- [ ] Handle image upload timeout/failure
- [ ] Handle audio playback errors (unsupported format, audio session conflicts)
- [ ] Graceful degradation when audio permissions denied (fall back to text-only)
- [ ] Handle server restart / session loss — prompt user to start new session

---

## Priority Order (suggested)

1. **Codegen pipeline** (§0) — sets up the type-safe foundation
2. **Wire protocol models** (§1) — define all message shapes in Pydantic
3. **Control socket hook** (§2) — the backbone for everything non-audio
4. **Sending messages** (§4) — basic text+image prompts
5. **Streaming text** (§7) — see agent responses live
6. **Tool calls & notifications** (§8) — see what the agent is doing
7. **Session history** (§9) — don't lose context on reconnect
8. **Global state** (§13) — clean architecture before things get complex
9. **Image upload** (§3) — send screenshots to the agent
10. **Audio socket hook** (§2) — dedicated binary channel
11. **Audio streaming out** (§5) — voice input to Voxtral
12. **Audio playback in** (§6) — TTS voice output, live conversation
13. **Interrupt system** (§10) — natural conversation flow
14. **Mode sync** (§12) — plan vs build
15. **Permission UI** (§11) — agent tool permissions
16. **Error handling** (§14) — polish
