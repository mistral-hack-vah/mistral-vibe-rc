"""
tests/manual_mic_test.py — Manual microphone + transcription sanity check
=========================================================================
Run with:
    python tests/manual_mic_test.py

What it does:
  1. Lists all available audio input devices so you can pick the right one.
  2. Streams audio from your mic through VoxtralAudioProcessor (same pipeline
     the server uses) until you press Ctrl+C.
  3. Prints partial transcripts on the same line as you speak, then prints
     final transcripts on a new line when you pause.

Requires MISTRAL_API_KEY to be set in your environment.
"""

import asyncio
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

from python.audio_processor import VoxtralAudioProcessor

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
    processor = VoxtralAudioProcessor()
    processor.reset(SESSION_ID)

    p = pyaudio.PyAudio()
    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        input_device_index=device_index,
        frames_per_buffer=CHUNK,
    )

    print("\nListening... speak into your mic. Press Ctrl+C to stop.\n")

    try:
        while True:
            data = stream.read(CHUNK, exception_on_overflow=False)
            energy = rms(data)
            bar = vu_bar(energy)

            result = await processor.process_audio(data, SESSION_ID)

            partial = result.get("partial")
            final = result.get("final")

            if final:
                # Clear the partial line, then print the final on its own line
                sys.stdout.write("\r" + " " * 80 + "\r")
                print(f"[TRANSCRIPT] {final}")
            elif partial:
                sys.stdout.write(f"\r{bar} {partial}...")
                sys.stdout.flush()
            else:
                sys.stdout.write(f"\r{bar}")
                sys.stdout.flush()

    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        print("\n\nStopped.")


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
