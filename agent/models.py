from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class Event(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    source: str
    title: str
    summary: str
    url: HttpUrl | str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def fingerprint(self) -> str:
        stable_parts = [
            self.source.strip().lower(),
            self.id.strip().lower(),
            self.title.strip().lower(),
            str(self.url).strip().lower(),
        ]
        return sha256("|".join(stable_parts).encode("utf-8")).hexdigest()

    def to_prompt_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class NotificationDecision(BaseModel):
    notify: bool
    priority: int = Field(ge=1, le=10)
    subject: str = Field(min_length=1)
    body: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class AgentRunResult(BaseModel):
    collected: int
    considered: int
    notified: int
    skipped_duplicates: int
    skipped_old: int
    tool_errors: int = 0
    decision_errors: int = 0
    notification_errors: int = 0
    memory_errors: int = 0
