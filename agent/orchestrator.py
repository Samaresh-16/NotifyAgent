from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Protocol, Sequence

from agent.memory import JsonMemory
from agent.models import AgentRunResult, Event, NotificationDecision


NotificationItem = tuple[Event, NotificationDecision]


class Tool(Protocol):
    name: str

    def collect(self) -> list[Event]:
        ...


class LlmDecisionClient(Protocol):
    def decide(self, event: Event) -> NotificationDecision:
        ...


class NotificationSender(Protocol):
    def send(self, subject: str, body: str) -> None:
        ...


class Orchestrator:
    def __init__(
        self,
        tools: Sequence[Tool],
        llm_client: LlmDecisionClient,
        notification_sender: NotificationSender,
        memory: JsonMemory,
        max_event_age: timedelta | None = timedelta(days=7),
    ) -> None:
        self.tools = tools
        self.llm_client = llm_client
        self.notification_sender = notification_sender
        self.memory = memory
        self.max_event_age = max_event_age

    def run(self) -> AgentRunResult:
        self.memory.load()
        events = self._collect_events()
        unique_events, in_run_duplicates = self._deduplicate(events)

        considered = 0
        notification_items: list[NotificationItem] = []
        skipped_duplicates = in_run_duplicates
        skipped_old = 0

        for event in unique_events:
            if self._is_too_old(event):
                skipped_old += 1
                continue

            event_hash = event.fingerprint
            if self.memory.has_notified(event_hash):
                skipped_duplicates += 1
                continue

            considered += 1
            decision = self.llm_client.decide(event)
            if decision.notify:
                notification_items.append((event, decision))

        if notification_items:
            self.notification_sender.send(
                subject=self._format_digest_subject(notification_items),
                body=self._format_digest_body(notification_items),
            )
            for event, _decision in notification_items:
                self.memory.mark_notified(event.fingerprint)

        self.memory.save()
        return AgentRunResult(
            collected=len(events),
            considered=considered,
            notified=len(notification_items),
            skipped_duplicates=skipped_duplicates,
            skipped_old=skipped_old,
        )

    def _collect_events(self) -> list[Event]:
        events: list[Event] = []
        for tool in self.tools:
            events.extend(tool.collect())
        return events

    def _deduplicate(self, events: Sequence[Event]) -> tuple[list[Event], int]:
        seen: set[str] = set()
        unique: list[Event] = []

        for event in events:
            fingerprint = event.fingerprint
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            unique.append(event)

        return unique, len(events) - len(unique)

    def _is_too_old(self, event: Event) -> bool:
        if self.max_event_age is None:
            return False

        event_time = event.timestamp
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)

        return datetime.now(timezone.utc) - event_time > self.max_event_age

    def _format_digest_subject(self, items: Sequence[NotificationItem]) -> str:
        highest_priority = max(decision.priority for _event, decision in items)
        if len(items) == 1:
            return items[0][1].subject
        return f"{len(items)} game and Bengaluru alerts worth your attention (top priority {highest_priority}/10)"

    def _format_digest_body(self, items: Sequence[NotificationItem]) -> str:
        sorted_items = sorted(
            items,
            key=lambda item: (item[1].priority, item[0].timestamp),
            reverse=True,
        )
        lines = [
            "Here are the interesting game deals, game releases, and Bengaluru updates from this run.",
            "",
            f"Total items: {len(sorted_items)}",
            "",
        ]

        for index, (event, decision) in enumerate(sorted_items, start=1):
            lines.extend(
                [
                    f"{index}. {decision.subject}",
                    f"   Priority: {decision.priority}/10",
                    f"   Source: {event.source}",
                    f"   Title: {event.title}",
                    f"   Summary: {decision.body}",
                    f"   Why it matters: {decision.reason}",
                    f"   Link: {event.url}",
                    f"   Published: {event.timestamp.isoformat()}",
                    "",
                ]
            )

        return "\n".join(lines).rstrip() + "\n"
