from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sys
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
    def send(self, subject: str, body: str | None = None, html: str | None = None) -> None:
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
        memory_errors = 0
        try:
            self.memory.load()
        except Exception as error:
            memory_errors += 1
            self._warn(f"Could not load memory; continuing with empty state: {error}")

        events = self._collect_events()
        unique_events, in_run_duplicates = self._deduplicate(events)

        considered = 0
        notification_items: list[NotificationItem] = []
        skipped_duplicates = in_run_duplicates
        skipped_old = 0
        decision_errors = 0
        notification_errors = 0

        for event in unique_events:
            if self._is_too_old(event):
                skipped_old += 1
                continue

            event_hash = event.fingerprint
            if self.memory.has_notified(event_hash):
                skipped_duplicates += 1
                continue

            considered += 1
            try:
                decision = self.llm_client.decide(event)
            except Exception as error:
                decision_errors += 1
                self._warn(
                    f"Decision failed for event {event.source}/{event.id}; skipping: {error}"
                )
                continue

            if decision.notify:
                notification_items.append((event, decision))

        if notification_items:
            try:
                html = self._render_html_digest(notification_items)
                self.notification_sender.send(
                    subject=self._format_digest_subject(notification_items),
                    body=self._format_digest_body(notification_items),
                    html=html,
                )
            except Exception as error:
                notification_errors += 1
                self._warn(f"Notification send failed; events will be retried later: {error}")
            else:
                for event, _decision in notification_items:
                    self.memory.mark_notified(event.fingerprint)

        try:
            self.memory.save()
        except Exception as error:
            memory_errors += 1
            self._warn(f"Could not save memory: {error}")

        return AgentRunResult(
            collected=len(events),
            considered=considered,
            notified=0 if notification_errors else len(notification_items),
            skipped_duplicates=skipped_duplicates,
            skipped_old=skipped_old,
            tool_errors=getattr(self, "_last_tool_errors", 0),
            decision_errors=decision_errors,
            notification_errors=notification_errors,
            memory_errors=memory_errors,
        )

    def _collect_events(self) -> list[Event]:
        events: list[Event] = []
        tool_errors = 0
        for tool in self.tools:
            try:
                events.extend(tool.collect())
            except Exception as error:
                tool_errors += 1
                self._warn(f"Tool {tool.name} failed; continuing without it: {error}")
        self._last_tool_errors = tool_errors
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

    def _render_html_digest(self, items: Sequence[NotificationItem]) -> str | None:
        try:
            from notifications.email_renderer import EmailRenderer

            return EmailRenderer().render(items)
        except Exception as error:
            self._warn(f"HTML email rendering failed; sending plain text only: {error}")
            return None

    def _warn(self, message: str) -> None:
        print(f"[WARN] {message}", file=sys.stderr)
