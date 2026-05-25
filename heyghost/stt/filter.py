from __future__ import annotations

import re
from dataclasses import dataclass


DEFAULT_IGNORED_PHRASES = (
    "thank you for watching",
    "thanks for watching",
    "see you in the next video",
    "visit our website",
    "for more information please visit me",
    "for more information visit me",
    "beadaholique",
    "yeah",
)

WAKE_PHRASES = (
    "hey ghost",
    "hello ghost",
    "hi ghost",
    "hey jarvis",
)


@dataclass(frozen=True)
class CorrectionResult:
    original_text: str
    cleaned_text: str
    corrected: bool
    reason: str = ""


class TranscriptFilter:
    def __init__(self, ignored_phrases: tuple[str, ...] = ()) -> None:
        self.ignored_phrases = tuple(
            self._normalize(item)
            for item in (*DEFAULT_IGNORED_PHRASES, *ignored_phrases)
            if item.strip()
        )

    def clean(self, text: str) -> str:
        return self.clean_with_result(text).cleaned_text

    def clean_with_result(self, text: str) -> CorrectionResult:
        cleaned = " ".join(text.strip().split())
        if not cleaned:
            return CorrectionResult(text, "", False, "empty")

        normalized = self._normalize(cleaned)
        if self._is_ignored(normalized):
            return CorrectionResult(text, "", True, "ignored_phrase")
        if self._is_repeated_filler(normalized):
            return CorrectionResult(text, "", True, "repeated_filler")
        corrected = self._correct_common_misrecognitions(normalized)
        if corrected:
            return CorrectionResult(text, corrected, True, "common_misrecognition")
        wake_removed = self._remove_wake_phrase(normalized)
        if wake_removed != normalized:
            return CorrectionResult(text, wake_removed, True, "wake_phrase_removed")
        return CorrectionResult(text, cleaned, False, "")

    def _is_ignored(self, normalized: str) -> bool:
        return any(phrase in normalized for phrase in self.ignored_phrases)

    def _is_repeated_filler(self, normalized: str) -> bool:
        words = normalized.split()
        if len(words) < 4 or len(words) % 2:
            return False
        half = len(words) // 2
        return words[:half] == words[half:]

    def _normalize(self, text: str) -> str:
        return re.sub(r"[^a-z0-9 ]+", "", text.lower()).strip()

    def _remove_wake_phrase(self, normalized: str) -> str:
        for phrase in WAKE_PHRASES:
            if normalized == phrase:
                return ""
            if normalized.startswith(f"{phrase} "):
                return normalized.removeprefix(f"{phrase} ").strip()
        return normalized

    def _correct_common_misrecognitions(self, normalized: str) -> str:
        corrections = {
            "what is he older": "what is yoga",
            "what is older": "what is yoga",
            "what is yoda": "what is yoga",
            "what is yoghurt": "what is yoga",
            "what is you got": "what is yoga",
            "what is my un": "what is spyware",
            "what is my u n": "what is spyware",
            "what is spy wear": "what is spyware",
            "what is spy where": "what is spyware",
            "what is spy random": "what is spyware",
            "what is a spy random": "what is spyware",
            "what is spire": "what is spyware",
            "what is spireware": "what is spyware",
            "what is ransom web": "what is ransomware",
            "what is ransom where": "what is ransomware",
            "what is ransom wear": "what is ransomware",
            "what are you david little": "what are your capabilities",
            "what are you doing with me": "what are your capabilities",
            "what are you giving me": "what are your capabilities",
            "what are you kiwi b": "what are your capabilities",
            "what are you qb": "what are your capabilities",
            "what are your cap abilities": "what are your capabilities",
            "what are your capablties": "what are your capabilities",
            "what are your capblities": "what are your capabilities",
            "what are your capability": "what are your capabilities",
            "show your capability": "show your llm capabilities",
            "show your cap abilities": "show your llm capabilities",
            "show your capablties": "show your llm capabilities",
            "what is coming through today usb": "what is connected to the usb",
            "what is coming through the usb": "what is connected to the usb",
            "what is connected today usb": "what is connected to the usb",
            "what is connecting to usb": "what is connected to the usb",
            "what is connecting to the usb": "what is connected to the usb",
            "what is connected usb": "what is connected to the usb",
            "wifi and this": "list files",
            "wi fi and this": "list files",
            "please twice": "list files",
            "please find": "list files",
            "list file": "list files",
            "less files": "list files",
            "this files": "list files",
            "short disk space": "show disk space",
            "show all this space": "show disk space",
            "sure did": "show disk space",
            "ghost birmingham": "show memory",
            "show network address": "show network address",
            "close that mean all": "close terminal",
            "close that mean that": "close terminal",
            "close the mean all": "close terminal",
            "close the mean that": "close terminal",
            "close mean all": "close terminal",
            "close mean that": "close terminal",
            "close birmingham": "close terminal",
            "close to the winner": "close terminal",
            "close the winner": "close terminal",
            "close to our winner": "close terminal",
            "close tour winner": "close terminal",
            "close the tour winner": "close terminal",
            "close terminal window": "close terminal",
            "close the terminal window": "close terminal",
            "close qterminal": "close terminal",
            "contoncy": "close terminal",
            "take one": "close terminal",
            "ghost terminal": "close terminal",
            "close terminal": "close terminal",
            "open a company now": "open terminal",
            "open company now": "open terminal",
            "open tell me now": "open terminal",
            "open domain": "open terminal",
            "open the menu": "open terminal",
            "open menu": "open terminal",
            "open that data menu": "open terminal",
            "open data menu": "open terminal",
            "open the window": "open terminal",
            "open window": "open terminal",
            "open that window": "open terminal",
            "are you home at every but never never never": "open terminal",
        }
        if normalized in corrections:
            return corrections[normalized]
        if normalized.startswith("what is ") and normalized.endswith(" older"):
            return normalized.removesuffix(" older") + " yoga"
        return ""
