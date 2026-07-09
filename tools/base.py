from __future__ import annotations

from typing import Protocol

from agent.models import Event


class BaseTool(Protocol):
    name: str

    def collect(self) -> list[Event]:
        ...

