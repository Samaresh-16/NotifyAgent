from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field


class MemoryState(BaseModel):
    notified_event_hashes: set[str] = Field(default_factory=set)


class JsonMemory:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.state = MemoryState()

    def load(self) -> MemoryState:
        if not self.path.exists():
            self.state = MemoryState()
            return self.state

        with self.path.open("r", encoding="utf-8") as file:
            raw = json.load(file)
        self.state = MemoryState.model_validate(raw)
        return self.state

    def has_notified(self, event_hash: str) -> bool:
        return event_hash in self.state.notified_event_hashes

    def mark_notified(self, event_hash: str) -> None:
        self.state.notified_event_hashes.add(event_hash)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.state.model_dump(mode="json")
        payload["notified_event_hashes"] = sorted(payload["notified_event_hashes"])
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2)
            file.write("\n")

