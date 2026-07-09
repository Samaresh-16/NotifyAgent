from __future__ import annotations

from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from datetime import datetime
from typing import Sequence

from agent.models import Event, NotificationDecision


class EmailRenderer:
    def __init__(self) -> None:
        template_dir = Path(__file__).parent / "templates"
        self.env = Environment(loader=FileSystemLoader(template_dir), autoescape=True)

    def _priority_label(self, priority_value: int) -> str:
        if priority_value >= 8:
            return "HIGH"
        if priority_value >= 4:
            return "MEDIUM"
        return "LOW"

    def render(self, notification_items: Sequence[tuple[Event, NotificationDecision]]) -> str:
        template = self.env.get_template("digest.html")

        notifications = []
        for event, decision in notification_items:
            label = self._priority_label(decision.priority)
            notifications.append(
                {
                    "priority": label,
                    "subject": decision.subject,
                    "body": decision.body,
                    "reason": decision.reason,
                    "event": {"source": event.source, "url": str(event.url)},
                }
            )

        stats = {
            "total": len(notifications),
            "high": len([n for n in notifications if n["priority"] == "HIGH"]),
            "medium": len([n for n in notifications if n["priority"] == "MEDIUM"]),
            "low": len([n for n in notifications if n["priority"] == "LOW"]),
            "date": datetime.now().strftime("%d %b %Y"),
        }

        return template.render(notifications=notifications, stats=stats)
