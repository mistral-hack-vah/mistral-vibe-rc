"""
tests/manual_mic_test.py — Manual microphone + transcription sanity check
=========================================================================
Run with:
    python tests/manual_mic_test.py

What it does:
  1. Lists all available audio input devices so you can pick the right one.
  2. Records audio from your mic using PushToTalkProcessor.
  3. Press Enter to transcribe the current recording, Ctrl+C to stop.

Requires MISTRAL_API_KEY to be set in your environment.
"""

import asyncio
import select
import sys
import os

# Ensure the project root is on the path when run directly
_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _ROOT)

# Load .env from project root if present
_env_path = os.path.join(_ROOT, ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                os.environ.setdefault(_k.strip(), _v.strip())

import numpy as np
import pyaudio

from python.audio_processor import PushToTalkProcessor

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
RATE = 16_000
CHANNELS = 1
CHUNK = 1024          # ~64 ms per chunk at 16 kHz
FORMAT = pyaudio.paInt16
SESSION_ID = "manual-test"

BAR_WIDTH = 30
ENERGY_SCALE = 10.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def list_input_devices(p: pyaudio.PyAudio) -> list[dict]:
    devices = []
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info["maxInputChannels"] > 0:
            devices.append({"index": i, "name": info["name"]})
    return devices


def rms(chunk_bytes: bytes) -> float:
    pcm = np.frombuffer(chunk_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    return float(np.sqrt(np.mean(np.square(pcm)) + 1e-12))


def vu_bar(energy: float) -> str:
    filled = min(int(energy * ENERGY_SCALE * BAR_WIDTH), BAR_WIDTH)
    return "[" + "#" * filled + "-" * (BAR_WIDTH - filled) + "]"


# ---------------------------------------------------------------------------
# Main async loop
# ---------------------------------------------------------------------------

async def run(device_index: int):
    processor = PushToTalkProcessor()
    processor.start_recording(SESSION_ID)

    p = pyaudio.PyAudio()
    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        input_device_index=device_index,
        frames_per_buffer=CHUNK,
    )

    print("\nRecording... speak into your mic.")
    print("Press Enter to transcribe, Ctrl+C to stop.\n")

    try:
        while True:
            data = stream.read(CHUNK, exception_on_overflow=False)
            energy = rms(data)
            bar = vu_bar(energy)

            # Append audio to buffer
            processor.append_audio(SESSION_ID, data)

            # Show VU meter and buffer duration
            duration_ms = processor.get_buffer_duration_ms(SESSION_ID)
            duration_sec = duration_ms / 1000
            sys.stdout.write(f"\r{bar} Recording: {duration_sec:.1f}s")
            sys.stdout.flush()

            # Check for Enter key (non-blocking)
            if select.select([sys.stdin], [], [], 0)[0]:
                sys.stdin.readline()  # consume the newline
                sys.stdout.write("\r" + " " * 60 + "\r")
                print("Transcribing...")

                text = await processor.stop_and_transcribe(SESSION_ID)
                if text:
                    print(f"[TRANSCRIPT] {text}\n")
                else:
                    print("[TRANSCRIPT] (no speech detected)\n")

                # Start recording again
                processor.start_recording(SESSION_ID)
                print("Recording... (press Enter to transcribe, Ctrl+C to stop)")

    except (KeyboardInterrupt, asyncio.CancelledError):
        # Transcribe any remaining audio on exit
        sys.stdout.write("\r" + " " * 60 + "\r")
        print("\nTranscribing final audio...")
        text = await processor.stop_and_transcribe(SESSION_ID)
        if text:
            print(f"[FINAL TRANSCRIPT] {text}")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        print("\nStopped.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    p = pyaudio.PyAudio()

    devices = list_input_devices(p)
    if not devices:
        print("ERROR: No audio input devices found.")
        p.terminate()
        sys.exit(1)

    print("\n=== Available input devices ===")
    for d in devices:
        print(f"  [{d['index']}] {d['name']}")

    default_idx = int(p.get_default_input_device_info()["index"])
    p.terminate()

    raw = input(f"\nDevice index (Enter for default [{default_idx}]): ").strip()
    device_index = int(raw) if raw else default_idx

    asyncio.run(run(device_index))


if __name__ == "__main__":
    main()
