# Mistral Vibe — Voice-Controlled Coding Assistant

Real-time voice agent that lets you talk to a Mistral-powered coding assistant. Speak, see your words transcribed live, get a spoken response, and watch code edits appear in real time.

## Architecture

```
Mobile App (Expo)  ←— WebSocket + REST SSE —→  Python Backend (FastAPI)
                                                   ├── Mistral Voxtral (realtime transcription)
                                                   ├── Mistral Vibe Agent (code generation)
                                                   └── ElevenLabs (text-to-speech)
```

## Prerequisites

- [mise](https://mise.jdx.dev/) — installs Node, pnpm, Python
- [uv](https://docs.astral.sh/uv/) — Python package manager
- API keys: **Mistral** and **ElevenLabs**

## Setup

### 1. Install dependencies

```bash
mise install          # node, pnpm, python
pnpm install          # JS dependencies
uv sync               # Python dependencies (creates .venv)
```

### 2. Configure environment variables

Create a `.env` file in the project root:

```bash
MISTRAL_API_KEY=<your-mistral-api-key>
ELEVENLABS_API_KEY=<your-elevenlabs-api-key>
```

### 3. Generate a dev JWT token for the mobile app

```bash
python apps/mobile/scripts/gen_dev_token.py
```

Then create `apps/mobile/.env`:

```bash
EXPO_PUBLIC_API_URL=http://<your-hostname-or-lan-ip>:8000
EXPO_PUBLIC_JWT_TOKEN=<paste-token-from-above>
```

### 4. Start the backend

```bash
uv run uvicorn python.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. Start the mobile app

```bash
# Web (browser)
pnpm dev:web

# iOS / Android
pnpm dev:mobile
```

## How It Works

1. **Press mic** — audio streams over WebSocket as PCM16 16kHz mono chunks
2. **Realtime transcription** — chunks stream to Mistral Voxtral, transcript deltas appear live in the chat
3. **Release mic** — final transcript sent to the Mistral Vibe agent
4. **Agent responds** — text streams back sentence-by-sentence
5. **TTS** — each sentence streams to ElevenLabs, audio chunks stream back to the app for playback
6. **Code edits** — any file changes the agent makes appear as diffs in the chat

## Project Structure

```
apps/
  mobile/               Expo React Native app
    hooks/
      use-agent.ts        Central orchestrator (messages, status)
      use-audio-socket.ts WebSocket connection + event parsing
      use-audio-playback.ts Low-latency TTS audio playback
      config.ts           Server URL + auth config
    components/chat/
      input-modal.tsx     Mic recording UI + waveform
python/
  main.py               FastAPI server (REST + WebSocket)
  audio_processor.py    Realtime streaming transcription (Voxtral)
  tts_service.py        ElevenLabs TTS streaming
  vibe_agent.py         Mistral Vibe agent wrapper
  session_manager.py    In-memory session state
  microphone_client.py  CLI push-to-talk test client
```

## Environment Variables

### Backend (root `.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `MISTRAL_API_KEY` | Yes | Mistral API key |
| `ELEVENLABS_API_KEY` | Yes | ElevenLabs API key for TTS |
| `ELEVENLABS_VOICE_ID` | No | Voice ID (default: Adam) |
| `JWT_SECRET` | No | JWT signing secret (default: `dev-secret-change-me`) |
| `VOXTRAL_REALTIME_MODEL` | No | Transcription model (default: `voxtral-mini-transcribe-realtime-2602`) |

### Mobile (`apps/mobile/.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `EXPO_PUBLIC_API_URL` | Yes | Backend URL (e.g. `http://victors-macbook-pro:8000`) |
| `EXPO_PUBLIC_JWT_TOKEN` | Yes | Dev JWT token (generate with script above) |

## CLI Test Client

Test the voice pipeline without the mobile app:

```bash
uv run python -m python.microphone_client
```

Press ENTER to start/stop recording. Requires a microphone and `pyaudio`.
