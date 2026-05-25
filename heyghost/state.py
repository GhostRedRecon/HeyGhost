from enum import Enum


class AssistantState(str, Enum):
    IDLE = "idle"
    IDLE_WAKE_WORD = "idle_wake_word"
    WAKE_DETECTED = "wake_detected"
    ACTIVE_SESSION = "active_session"
    ACTIVE_LISTENING = "active_listening"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    SPEAKING = "speaking"
    FOLLOW_UP_LISTENING = "follow_up_listening"
