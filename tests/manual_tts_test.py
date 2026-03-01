"""
Manual TTS test — streams a sentence through ElevenLabs and saves it to test_tts_output.mp3.

Run from the repo root:
    uv run python tests/manual_tts_test.py

Then open test_tts_output.mp3 to hear the result.
"""

import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from python.tts_service import stream_tts

TEST_TEXT = "Hello! This is a test of the ElevenLabs text to speech system. If you can hear this, it's working correctly."
OUTPUT_FILE = "test_tts_output.mp3"


async def main() -> None:
    print(f"API key set: {'yes' if os.environ.get('ELEVENLABS_API_KEY') else 'NO — check .env'}")
    print(f"Streaming TTS to {OUTPUT_FILE} ...")

    total = 0
    with open(OUTPUT_FILE, "wb") as f:
        async for chunk in stream_tts(TEST_TEXT):
            f.write(chunk)
            total += len(chunk)
            print(f"  received {len(chunk)} bytes (total {total})", end="\r")

    print(f"\nDone — wrote {total} bytes to {OUTPUT_FILE}")
    print(f"Open {OUTPUT_FILE} to hear the audio.")


if __name__ == "__main__":
    asyncio.run(main())
