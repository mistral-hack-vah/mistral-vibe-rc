# tests/test_audio_processor.py
"""
Unit tests for PushToTalkProcessor.

These tests don't require MISTRAL_API_KEY - they test the buffering logic only.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestPushToTalkProcessor:
    @pytest.fixture
    def processor(self):
        """Create a processor with mocked Mistral client."""
        with patch.dict("os.environ", {"MISTRAL_API_KEY": "test-key"}):
            with patch("python.audio_processor.Mistral") as mock_mistral:
                from python.audio_processor import PushToTalkProcessor
                proc = PushToTalkProcessor()
                proc._client = mock_mistral.return_value
                return proc

    def test_start_recording(self, processor):
        processor.start_recording("session-1")
        assert processor.is_recording("session-1")
        assert "session-1" in processor._buffers

    def test_start_recording_clears_previous_buffer(self, processor):
        processor._buffers["session-1"] = bytearray(b"\x01\x02\x03")
        processor.start_recording("session-1")
        assert len(processor._buffers["session-1"]) == 0

    def test_is_recording_false_by_default(self, processor):
        assert not processor.is_recording("nonexistent")

    def test_append_audio(self, processor):
        processor.start_recording("session-1")
        processor.append_audio("session-1", b"\x01\x02")
        processor.append_audio("session-1", b"\x03\x04")
        assert bytes(processor._buffers["session-1"]) == b"\x01\x02\x03\x04"

    def test_append_audio_auto_starts(self, processor):
        """Appending to non-existent buffer should auto-start."""
        processor.append_audio("session-1", b"\x01\x02")
        assert processor.is_recording("session-1")
        assert bytes(processor._buffers["session-1"]) == b"\x01\x02"

    def test_cancel_recording(self, processor):
        processor.start_recording("session-1")
        processor.append_audio("session-1", b"\x01\x02\x03\x04")
        processor.cancel_recording("session-1")

        assert not processor.is_recording("session-1")
        assert "session-1" not in processor._buffers

    def test_get_buffer_duration_ms(self, processor):
        processor.start_recording("session-1")
        # 16000 samples/sec * 2 bytes/sample = 32000 bytes/sec
        # 1600 bytes = 0.05 sec = 50ms
        processor.append_audio("session-1", b"\x00" * 1600)
        duration = processor.get_buffer_duration_ms("session-1")
        assert duration == 50

    def test_get_buffer_duration_empty(self, processor):
        assert processor.get_buffer_duration_ms("nonexistent") == 0

    @pytest.mark.asyncio
    async def test_stop_and_transcribe_empty(self, processor):
        """Empty buffer should return empty string."""
        result = await processor.stop_and_transcribe("nonexistent")
        assert result == ""

    @pytest.mark.asyncio
    async def test_stop_and_transcribe_calls_api(self, processor):
        """Should call Mistral transcription API with WAV-wrapped audio."""
        processor.start_recording("session-1")
        processor.append_audio("session-1", b"\x00" * 3200)  # 100ms of silence

        # Mock the transcription response
        mock_response = MagicMock()
        mock_response.text = "transcribed text"
        processor._client.audio.transcriptions.complete_async = AsyncMock(
            return_value=mock_response
        )

        result = await processor.stop_and_transcribe("session-1")

        assert result == "transcribed text"
        assert not processor.is_recording("session-1")
        processor._client.audio.transcriptions.complete_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_and_transcribe_clears_buffer(self, processor):
        """After transcription, buffer should be cleared."""
        processor.start_recording("session-1")
        processor.append_audio("session-1", b"\x00" * 1600)

        mock_response = MagicMock()
        mock_response.text = "hello"
        processor._client.audio.transcriptions.complete_async = AsyncMock(
            return_value=mock_response
        )

        await processor.stop_and_transcribe("session-1")

        assert "session-1" not in processor._buffers

    @pytest.mark.asyncio
    async def test_stop_and_transcribe_handles_api_error(self, processor):
        """API errors should return empty string, not crash."""
        processor.start_recording("session-1")
        processor.append_audio("session-1", b"\x00" * 1600)

        processor._client.audio.transcriptions.complete_async = AsyncMock(
            side_effect=Exception("API error")
        )

        result = await processor.stop_and_transcribe("session-1")

        assert result == ""

    def test_pcm16_to_wav(self, processor):
        """Should create valid WAV header."""
        pcm = b"\x00\x00" * 100  # 100 samples of silence
        wav = processor._pcm16_to_wav(pcm)

        # WAV files start with "RIFF"
        assert wav[:4] == b"RIFF"
        # Should contain "WAVE" format
        assert b"WAVE" in wav[:20]