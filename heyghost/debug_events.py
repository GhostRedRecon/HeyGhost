from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class DebugEventStream:
    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def reset(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("", encoding="utf-8")
        except OSError:
            return

    def emit(self, event: str, text: str = "", **fields: Any) -> None:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "event": event,
        }
        if text:
            payload["text"] = text
        payload.update(fields)
        self.emit_payload(payload)

    def emit_payload(self, payload: dict[str, Any]) -> None:
        record = dict(payload)
        record.setdefault(
            "ts",
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )

        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                json.dump(record, handle, ensure_ascii=True)
                handle.write("\n")
        except OSError:
            return
