from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol


class CleanupProvider(Protocol):
    def cleanup(self, text: str, *, context: str = "") -> str: ...


@dataclass(slots=True)
class CleanupDecision:
    text: str
    needs_model: bool
    reason: str = ""


@dataclass(slots=True)
class RuleCleaner:
    """Fast English dictation pre-cleaner.

    This intentionally handles deterministic transformations before any model
    is considered, keeping S1-mini unloaded for simple utterances.
    """

    fillers: tuple[str, ...] = ("um", "uh", "erm", "hmm")

    _semantic_markers = (
        " actually ", " i mean ", " no make that ", " rather ",
        " correction ", " scratch that ", " instead ",
    )

    def cleanup(self, text: str, *, context: str = "") -> str:
        s = f" {text.strip()} "
        # Spoken structural commands first. Keep replacements conservative.
        replacements = (
            (r"\b(?:new|next) line\b", "\n"),
            (r"\bnew paragraph\b", "\n\n"),
            (r"\bquestion mark\b", "?"),
            (r"\bexclamation (?:mark|point)\b", "!"),
            (r"\bcomma\b", ","),
            (r"\bsemicolon\b", ";"),
            (r"\bcolon\b", ":"),
            (r"\bfull stop\b|\bperiod\b", "."),
            (r"\bdot com\b", ".com"),
            (r"\bdot org\b", ".org"),
            (r"\bdot net\b", ".net"),
        )
        for pattern, repl in replacements:
            s = re.sub(pattern, repl, s, flags=re.IGNORECASE)

        # Remove a small set of unambiguous fillers. "like" is deliberately not
        # removed because it is often semantic English.
        filler_re = r"(?<!\w)(?:" + "|".join(re.escape(x) for x in self.fillers) + r")(?!\w)[, ]*"
        s = re.sub(filler_re, "", s, flags=re.IGNORECASE)

        # Collapse exact adjacent repeated words while preserving line breaks.
        s = re.sub(r"\b([A-Za-z][A-Za-z'-]*)\s+\1\b", r"\1", s, flags=re.IGNORECASE)
        # Normalize spaces around punctuation without destroying newlines.
        s = re.sub(r"[ \t]+([,.;:?!])", r"\1", s)
        s = re.sub(r"([,.;:?!])(?=[A-Za-z])", r"\1 ", s)
        # Undo sentence-spacing for common spoken URL TLDs.
        s = re.sub(r"\.\s+(com|org|net)\b", r".\1", s, flags=re.IGNORECASE)
        s = re.sub(r"[ \t]{2,}", " ", s)
        s = re.sub(r" *\n *", "\n", s)
        s = re.sub(r"\n{3,}", "\n\n", s)
        return s.strip()

    def route(self, text: str, *, context: str = "") -> CleanupDecision:
        cleaned = self.cleanup(text, context=context)
        padded = f" {cleaned.lower()} "
        for marker in self._semantic_markers:
            if marker in padded:
                return CleanupDecision(cleaned, True, f"semantic correction marker: {marker.strip()}")
        # Long or heavily disfluent utterances benefit from semantic cleanup;
        # short clean commands do not.
        words = cleaned.split()
        if len(words) >= 45:
            return CleanupDecision(cleaned, True, "long utterance")
        if re.search(r"\b(\w+)\s+\1\s+\1\b", cleaned, re.IGNORECASE):
            return CleanupDecision(cleaned, True, "repeated false start")
        return CleanupDecision(cleaned, False, "rules sufficient")


S1_SYSTEM_PROMPT = (
    "You are a text normalizer for speech-to-text transcripts. The input begins "
    "with a control line specifying the styling, structure, and context settings; "
    "clean the transcript to match those settings and output only the cleaned text."
)

S1_STYLING = ("casual", "semi-casual", "semi-formal", "formal")
S1_STRUCTURE = ("prose", "lists")
S1_CONTEXT = ("general", "email")


@dataclass(slots=True)
class S1MiniConfig:
    model_id: str = "S1-mini by Superwhisper"
    max_input_tokens: int = 1000
    max_output_tokens: int = 1024
    temperature: float = 0.0
    preferred_device_order: tuple[str, ...] = ("NPU", "GPU", "CPU")
    lazy_load: bool = True
    idle_unload_s: float = 45.0

    @staticmethod
    def output_budget(input_tokens: int) -> int:
        """Official sizing guidance: about 1.3x input + 32, capped safely."""
        return min(1024, max(32, int(input_tokens * 1.3 + 32)))

    @staticmethod
    def control_line(
        styling: str = "semi-formal",
        structure: str = "prose",
        context: str = "general",
    ) -> str:
        if styling not in S1_STYLING:
            raise ValueError(f"invalid S1-mini styling {styling!r}")
        if structure not in S1_STRUCTURE:
            raise ValueError(f"invalid S1-mini structure {structure!r}")
        if context not in S1_CONTEXT:
            raise ValueError(f"invalid S1-mini context {context!r}")
        return f"[Styling: {styling}] [Structure: {structure}] [Context: {context}]"

    @classmethod
    def messages(
        cls,
        transcript: str,
        styling: str = "semi-formal",
        structure: str = "prose",
        context: str = "general",
    ) -> list[dict[str, str]]:
        control = cls.control_line(styling, structure, context)
        return [
            {"role": "system", "content": S1_SYSTEM_PROMPT},
            {"role": "user", "content": f"{control}\n{transcript}"},
        ]


class S1MiniProvider:
    """Lazy interface for the optimized local English cleanup model.

    OpenVINO/llama.cpp imports belong inside a disposable runtime worker, not
    the Metatron control plane. The runtime must use S1MiniConfig.messages(),
    greedy decoding / temperature 0, and Qwen3 thinking disabled.
    """

    def __init__(self, config: S1MiniConfig | None = None):
        self.config = config or S1MiniConfig()

    def cleanup(self, text: str, *, context: str = "") -> str:
        raise RuntimeError(
            "S1-mini runtime adapter is not wired yet; benchmark OpenVINO GPU/NPU/CPU first"
        )



class S1MiniWorkerProvider:
    """Production control-plane adapter for a disposable S1-mini JSONL worker.

    The model/runtime stays out of the Metatron process. The worker command is
    supplied by packaging/user configuration and must implement `cleanup`.
    """
    def __init__(self, supervisor, config: S1MiniConfig | None = None):
        self.supervisor = supervisor
        self.config = config or S1MiniConfig()

    def cleanup(
        self, text: str, *, context: str = "general", styling: str = "semi-formal", structure: str = "prose"
    ) -> str:
        if context not in S1_CONTEXT:
            context = "general"
        messages = self.config.messages(text, styling=styling, structure=structure, context=context)
        result = self.supervisor.request("cleanup", {
            "text": text,
            "styling": styling,
            "structure": structure,
            "context": context,
            "messages": messages,
            "thinking": False,
            "temperature": 0.0,
            "max_output_tokens": self.config.output_budget(max(1, len(text.split()))),
        })
        if isinstance(result, dict):
            result = result.get("text", "")
        return str(result or "").strip()

    def stop(self) -> None:
        self.supervisor.stop()


@dataclass(slots=True)
class CleanupManager:
    rules: RuleCleaner
    semantic: CleanupProvider | None = None

    def cleanup(self, text: str, *, context: str = "general") -> dict[str, object]:
        decision = self.rules.route(text, context=context)
        if not decision.needs_model or self.semantic is None:
            return {
                "text": decision.text,
                "semantic_used": False,
                "semantic_available": self.semantic is not None,
                "reason": decision.reason,
            }
        output = self.semantic.cleanup(decision.text, context=context)
        return {
            "text": output,
            "semantic_used": True,
            "semantic_available": True,
            "reason": decision.reason,
        }
