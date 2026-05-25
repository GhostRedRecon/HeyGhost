from datetime import datetime


def run() -> str:
    return datetime.now().strftime("It is %H:%M on %A, %B %d.")
