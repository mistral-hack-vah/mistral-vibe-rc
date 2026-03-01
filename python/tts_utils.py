"""
Text cleaning and sentence extraction for TTS streaming.

Strips markdown, code blocks, and other non-speech content so that
only prose text is sent to the TTS engine. Also provides sentence-level
splitting for low-latency parallel TTS streaming.
"""

import re


def clean_for_tts(text: str) -> str:
    """Strip code, markdown formatting, and other non-speech content."""
    # Remove fenced code blocks (``` ... ```)
    text = re.sub(r"```[\s\S]*?```", " ", text)
    # Remove inline code (`...`)
    text = re.sub(r"`[^`]*`", "", text)
    # Remove markdown headers (#)
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    # Remove markdown bold/italic markers but keep text
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", text)
    # Remove markdown links, keep text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Remove images
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    # Remove horizontal rules
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Collapse multiple newlines into sentence breaks
    text = re.sub(r"\n{2,}", ". ", text)
    text = re.sub(r"\n", " ", text)
    # Collapse multiple spaces
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def extract_sentences(buffer: str) -> tuple[list[str], str]:
    """
    Extract complete sentences from a text buffer.

    Returns (complete_sentences, remaining_buffer).
    A sentence ends with `.`, `!`, or `?` followed by whitespace.
    """
    sentences: list[str] = []
    while True:
        match = re.search(r"[.!?]\s+", buffer)
        if not match:
            break
        end = match.end()
        sentence = buffer[:end].strip()
        buffer = buffer[end:]
        if sentence:
            sentences.append(sentence)
    return sentences, buffer
