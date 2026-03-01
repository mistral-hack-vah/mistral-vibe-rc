# python/intent_classifier.py
"""
Intent classifier for voice transcripts.

Classifies whether user input is:
  - "prompt": A conversational question/query for the AI to answer
  - "command": An instruction for the vibe CLI to execute (file operations, code generation, etc.)

Also cleans/normalizes the transcript for better processing.
"""

import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from mistralai import Mistral


class IntentType(str, Enum):
    PROMPT = "prompt"    # Conversational query
    COMMAND = "command"  # Action/instruction for vibe CLI


@dataclass
class ClassifiedIntent:
    """Result of intent classification."""
    intent: IntentType
    original_text: str
    cleaned_text: str
    confidence: float = 1.0


# Common filler words/phrases to remove from voice transcripts
FILLER_PATTERNS = [
    r"\b(um+|uh+|er+|ah+|hmm+)\b",
    r"\b(like|you know|i mean|basically|actually|literally)\b",
    r"\b(so+|well|okay|ok)\b(?=\s|$)",
    r"^\s*(hey|hi|hello)\s+",
]

# Politeness phrases to strip from commands
POLITENESS_PATTERNS = [
    r"\b(can you|could you|would you)\s+(please\s+)?",
    r"\b(please)\s+",
    r"\b(i want you to|i need you to|i'd like you to)\s+",
    r"\b(go ahead and|just|simply)\s+",
    r"\s*(please|thanks|thank you)\.?$",
    r"^(hey vibe|hey|vibe)\s*[,:]?\s*",
]

# Speech-to-text symbol mappings (spoken word -> actual symbol)
SYMBOL_MAPPINGS = [
    # File extensions and paths
    (r"\bdot\s+py\b", ".py"),
    (r"\bdot\s+ts\b", ".ts"),
    (r"\bdot\s+tsx\b", ".tsx"),
    (r"\bdot\s+js\b", ".js"),
    (r"\bdot\s+jsx\b", ".jsx"),
    (r"\bdot\s+json\b", ".json"),
    (r"\bdot\s+yaml\b", ".yaml"),
    (r"\bdot\s+yml\b", ".yml"),
    (r"\bdot\s+md\b", ".md"),
    (r"\bdot\s+txt\b", ".txt"),
    (r"\bdot\s+css\b", ".css"),
    (r"\bdot\s+html\b", ".html"),
    (r"\bdot\s+env\b", ".env"),
    (r"\bdot\s+toml\b", ".toml"),
    (r"\bdot\s+rs\b", ".rs"),
    (r"\bdot\s+go\b", ".go"),
    (r"\bdot\s+(\w+)\b", r".\1"),  # Generic: "dot X" -> ".X"
    # Paths
    (r"\bforward slash\b", "/"),
    (r"\bslash\b", "/"),
    (r"\bbackslash\b", "\\\\"),
    # Common symbols - use spaces around for joining words
    (r"\s+underscore\s+", "_"),
    (r"\bunderscore\b", "_"),
    (r"\s+hyphen\s+", "-"),
    (r"\bhyphen\b", "-"),
    (r"\s+dash\s+", "-"),
    (r"\bdash\b", "-"),
    (r"\bcolon\b", ":"),
    (r"\bsemicolon\b", ";"),
    (r"\bcomma\b", ","),
    (r"\bequals\b", "="),
    (r"\bequal sign\b", "="),
    (r"\bplus\b", "+"),
    (r"\bminus\b", "-"),
    (r"\basterisk\b", "*"),
    (r"\bstar\b", "*"),
    (r"\bat sign\b", "@"),
    (r"\bhash\b", "#"),
    (r"\bhashtag\b", "#"),
    (r"\bpound\b", "#"),
    (r"\bdollar sign\b", "$"),
    (r"\bdollar\b", "$"),
    (r"\bpercent\b", "%"),
    (r"\bampersand\b", "&"),
    (r"\band sign\b", "&"),
    (r"\bopen paren\b", "("),
    (r"\bclose paren\b", ")"),
    (r"\bopen bracket\b", "["),
    (r"\bclose bracket\b", "]"),
    (r"\bopen brace\b", "{"),
    (r"\bclose brace\b", "}"),
    (r"\bless than\b", "<"),
    (r"\bgreater than\b", ">"),
    (r"\bpipe\b", "|"),
    (r"\btilde\b", "~"),
    (r"\bbacktick\b", "`"),
    (r"\bsingle quote\b", "'"),
    (r"\bdouble quote\b", '"'),
    (r"\bnew line\b", "\n"),
    (r"\bspace\b(?=\s|$)", " "),
]

# Common spoken patterns to fix for commands
COMMAND_FIXES = [
    # "called X" -> just X (for file names)
    (r"\bcalled\s+", ""),
    (r"\bnamed\s+", ""),
    # "a file" -> "file" (remove articles in certain contexts)
    (r"\b(create|make|add)\s+a\s+new\s+", r"\1 "),
    (r"\b(create|make|add)\s+a\s+", r"\1 "),
    # "the file" -> "file"
    (r"\bthe\s+(file|folder|directory|function|class|component|module)\b", r"\1"),
    # Numbers spoken as words
    (r"\bone\b", "1"),
    (r"\btwo\b", "2"),
    (r"\bthree\b", "3"),
    (r"\bfour\b", "4"),
    (r"\bfive\b", "5"),
    (r"\bsix\b", "6"),
    (r"\bseven\b", "7"),
    (r"\beight\b", "8"),
    (r"\bnine\b", "9"),
    (r"\bten\b", "10"),
    (r"\bzero\b", "0"),
]

# Command indicator phrases (suggest vibe CLI action)
COMMAND_INDICATORS = [
    # File operations
    r"\b(create|make|write|generate|add)\s+(a\s+)?(new\s+)?(file|component|function|class|module)",
    r"\b(edit|modify|update|change|fix)\s+(the\s+)?",
    r"\b(delete|remove|rename)\s+(the\s+)?(file|function|class)",
    r"\b(run|execute|start|launch|build|test|deploy)",
    r"\b(install|add|remove)\s+(the\s+)?(package|dependency|module)",
    # Code actions
    r"\b(refactor|optimize|clean up|format)\b",
    r"\b(implement|add|create)\s+(a\s+)?(feature|functionality)",
    r"\b(fix|debug|solve)\s+(the\s+)?(bug|error|issue|problem)",
    # Git operations
    r"\b(commit|push|pull|merge|checkout|branch)\b",
    r"\b(git)\s+\w+",
    # Navigation
    r"\b(open|go to|navigate to|show me)\s+(the\s+)?",
    r"\b(find|search for|look for)\s+(the\s+)?",
    r"\b(list|show)\s+(all\s+)?(files|functions|classes)",
]

# Prompt indicator phrases (suggest conversational query)
PROMPT_INDICATORS = [
    r"^(what|why|how|when|where|who|which|can you|could you|would you)",
    r"\b(explain|tell me|describe|help me understand)\b",
    r"\?$",  # Ends with question mark
    r"\b(what is|what are|what does|how does|how do|why is|why does)\b",
    r"\b(difference between|compare|versus|vs)\b",
]


def _clean_transcript(text: str) -> str:
    """Remove filler words and normalize whitespace."""
    cleaned = text.strip()

    for pattern in FILLER_PATTERNS:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

    # Normalize whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Capitalize first letter
    if cleaned:
        cleaned = cleaned[0].upper() + cleaned[1:]

    return cleaned


def _clean_command(text: str) -> str:
    """
    Clean and normalize a command for the vibe CLI.

    Performs aggressive cleaning:
    - Removes politeness phrases
    - Converts spoken symbols to actual characters
    - Fixes common speech-to-text patterns
    - Normalizes file names and paths
    """
    cleaned = text.strip()

    # Remove politeness phrases
    for pattern in POLITENESS_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    # Remove filler words
    for pattern in FILLER_PATTERNS:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

    # Apply symbol mappings (spoken -> actual)
    for pattern, replacement in SYMBOL_MAPPINGS:
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)

    # Apply command-specific fixes
    for pattern, replacement in COMMAND_FIXES:
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)

    # Normalize whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Remove spaces around path separators
    cleaned = re.sub(r"\s*/\s*", "/", cleaned)
    cleaned = re.sub(r"\s*\\\s*", "\\\\", cleaned)

    # Remove spaces before file extensions
    cleaned = re.sub(r"\s+\.", ".", cleaned)

    # Capitalize first letter for readability
    if cleaned:
        cleaned = cleaned[0].upper() + cleaned[1:]

    return cleaned


def _classify_by_rules(text: str) -> Optional[IntentType]:
    """
    Rule-based classification as a fast first pass.
    Returns None if uncertain.
    """
    text_lower = text.lower()

    command_score = 0
    prompt_score = 0

    for pattern in COMMAND_INDICATORS:
        if re.search(pattern, text_lower):
            command_score += 1

    for pattern in PROMPT_INDICATORS:
        if re.search(pattern, text_lower):
            prompt_score += 1

    # Clear winner
    if command_score > prompt_score and command_score >= 2:
        return IntentType.COMMAND
    if prompt_score > command_score and prompt_score >= 2:
        return IntentType.PROMPT

    # Single strong indicator
    if command_score >= 1 and prompt_score == 0:
        return IntentType.COMMAND
    if prompt_score >= 1 and command_score == 0:
        return IntentType.PROMPT

    return None  # Uncertain, need LLM


class IntentClassifier:
    """
    Classifies voice transcripts into prompts vs commands.

    Uses rule-based classification first, falls back to Mistral LLM
    for ambiguous cases.
    """

    def __init__(self):
        api_key = os.environ.get("MISTRAL_API_KEY")
        self._client = Mistral(api_key=api_key) if api_key else None
        self._model = os.environ.get("MISTRAL_CLASSIFIER_MODEL", "mistral-small-latest")

    async def classify(self, transcript: str) -> ClassifiedIntent:
        """
        Classify a voice transcript.

        Args:
            transcript: Raw transcribed text from audio

        Returns:
            ClassifiedIntent with intent type and cleaned text
        """
        if not transcript or not transcript.strip():
            return ClassifiedIntent(
                intent=IntentType.PROMPT,
                original_text=transcript,
                cleaned_text="",
                confidence=0.0,
            )

        # Basic cleaning for classification
        basic_cleaned = _clean_transcript(transcript)

        # Try rule-based first
        rule_intent = _classify_by_rules(basic_cleaned)
        if rule_intent is not None:
            # Apply intent-specific cleaning
            if rule_intent == IntentType.COMMAND:
                final_text = _clean_command(transcript)
            else:
                final_text = basic_cleaned

            return ClassifiedIntent(
                intent=rule_intent,
                original_text=transcript,
                cleaned_text=final_text,
                confidence=0.9,
            )

        # Fall back to LLM for ambiguous cases
        if self._client:
            return await self._classify_with_llm(transcript, basic_cleaned)

        # Default to command if no LLM available (vibe can handle most things)
        return ClassifiedIntent(
            intent=IntentType.COMMAND,
            original_text=transcript,
            cleaned_text=_clean_command(transcript),
            confidence=0.5,
        )

    async def _classify_with_llm(self, original: str, cleaned: str) -> ClassifiedIntent:
        """Use Mistral to classify ambiguous input and clean it appropriately."""
        system_prompt = """You are an intent classifier for a voice-controlled coding assistant called "vibe".

Classify the user's input as either:
- "command": An instruction to perform an action (create file, run code, edit, git operations, etc.)
- "prompt": A conversational question or query that needs an explanation/answer

Respond with ONLY a JSON object: {"intent": "command" or "prompt", "cleaned": "improved version of input"}

For COMMANDS, the "cleaned" field should:
- Remove filler words (um, uh, like, you know)
- Remove politeness phrases (please, can you, I want you to)
- Convert spoken symbols to actual characters (dot py -> .py, slash -> /)
- Be a clear, actionable instruction for the vibe CLI
- Example: "um can you please create a new file called test dot py" -> "Create file test.py"

For PROMPTS, the "cleaned" field should:
- Remove filler words
- Keep the question clear and natural
- Example: "um like what is like async await" -> "What is async/await?"

Keep it concise and actionable."""

        try:
            response = await self._client.chat.complete_async(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Classify: {original}"},
                ],
                temperature=0.1,
                max_tokens=200,
            )

            result_text = response.choices[0].message.content.strip()

            # Parse JSON response
            import json
            # Handle markdown code blocks
            if "```" in result_text:
                match = re.search(r"```(?:json)?\s*(.*?)\s*```", result_text, re.DOTALL)
                result_text = match.group(1) if match else "{}"

            result = json.loads(result_text)
            intent = IntentType.COMMAND if result.get("intent") == "command" else IntentType.PROMPT

            # Get LLM's cleaned version, or fall back to our cleaning
            llm_cleaned = result.get("cleaned", "")
            if llm_cleaned:
                # Still apply our symbol mappings to LLM output for consistency
                if intent == IntentType.COMMAND:
                    final_text = _clean_command(llm_cleaned)
                else:
                    final_text = llm_cleaned
            else:
                # LLM didn't provide cleaned text, use our cleaning
                if intent == IntentType.COMMAND:
                    final_text = _clean_command(original)
                else:
                    final_text = cleaned

            return ClassifiedIntent(
                intent=intent,
                original_text=original,
                cleaned_text=final_text,
                confidence=0.85,
            )

        except Exception as e:
            print(f"[IntentClassifier] LLM error: {e}")
            # Default to command on error
            return ClassifiedIntent(
                intent=IntentType.COMMAND,
                original_text=original,
                cleaned_text=_clean_command(original),
                confidence=0.5,
            )


# Singleton instance
_classifier: Optional[IntentClassifier] = None


def get_intent_classifier() -> IntentClassifier:
    """Get or create the singleton IntentClassifier."""
    global _classifier
    if _classifier is None:
        _classifier = IntentClassifier()
    return _classifier
