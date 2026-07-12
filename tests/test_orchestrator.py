from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from agent.memory import JsonMemory
from agent.models import Event, NotificationDecision
from agent.orchestrator import Orchestrator


class FakeTool:
    name = "fake"

    def __init__(self, events: list[Event]) -> None:
        self.events = events

    def collect(self) -> list[Event]:
        return self.events


class FakeLlm:
    def __init__(self, decision: NotificationDecision) -> None:
        self.decision = decision
        self.calls = 0

    def decide(self, event: Event) -> NotificationDecision:
        self.calls += 1
        return self.decision


class MappingFakeLlm:
    def __init__(self, decisions: dict[str, NotificationDecision]) -> None:
        self.decisions = decisions
        self.calls = 0

    def decide(self, event: Event) -> NotificationDecision:
        self.calls += 1
        return self.decisions[event.id]


class FakeSender:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send(self, subject: str, body: str | None = None, html: str | None = None) -> None:
        self.sent.append((subject, body or ""))


class FailingTool:
    name = "failing"

    def collect(self) -> list[Event]:
        raise RuntimeError("tool unavailable")


class FailingLlm:
    def __init__(self) -> None:
        self.calls = 0

    def decide(self, event: Event) -> NotificationDecision:
        self.calls += 1
        raise RuntimeError("llm unavailable")


class FailingSender:
    def send(self, subject: str, body: str | None = None, html: str | None = None) -> None:
        raise RuntimeError("smtp unavailable")


def make_event(event_id: str = "1") -> Event:
    return Event(
        id=event_id,
        source="test",
        title="Important thing happened",
        summary="A concise summary",
        url=f"https://example.com/{event_id}",
        timestamp=datetime.now(timezone.utc),
    )


def test_orchestrator_sends_and_persists_notified_event(tmp_path: Path) -> None:
    event = make_event()
    llm = FakeLlm(
        NotificationDecision(
            notify=True,
            priority=8,
            subject="Worth knowing",
            body="This matters.",
            reason="It is relevant and timely.",
        )
    )
    sender = FakeSender()
    memory = JsonMemory(tmp_path / "state.json")

    result = Orchestrator([FakeTool([event])], llm, sender, memory).run()

    assert result.collected == 1
    assert result.considered == 1
    assert result.notified == 1
    assert len(sender.sent) == 1
    assert "This matters." in sender.sent[0][1]

    reloaded = JsonMemory(tmp_path / "state.json")
    reloaded.load()
    assert reloaded.has_notified(event.fingerprint)


def test_orchestrator_skips_in_run_and_memory_duplicates(tmp_path: Path) -> None:
    event = make_event()
    memory = JsonMemory(tmp_path / "state.json")
    memory.load()
    memory.mark_notified(event.fingerprint)
    memory.save()
    llm = FakeLlm(
        NotificationDecision(
            notify=True,
            priority=8,
            subject="Worth knowing",
            body="This matters.",
            reason="It is relevant and timely.",
        )
    )
    sender = FakeSender()

    result = Orchestrator([FakeTool([event, event])], llm, sender, memory).run()

    assert result.collected == 2
    assert result.considered == 0
    assert result.notified == 0
    assert result.skipped_duplicates == 2
    assert llm.calls == 0
    assert sender.sent == []


def test_orchestrator_batches_multiple_notifications_into_one_email(tmp_path: Path) -> None:
    first = make_event("1")
    second = make_event("2")
    quiet = make_event("3")
    llm = MappingFakeLlm(
        {
            "1": NotificationDecision(
                notify=True,
                priority=7,
                subject="First alert",
                body="First item body.",
                reason="First reason.",
            ),
            "2": NotificationDecision(
                notify=True,
                priority=9,
                subject="Second alert",
                body="Second item body.",
                reason="Second reason.",
            ),
            "3": NotificationDecision(
                notify=False,
                priority=1,
                subject="Quiet item",
                body="No need to notify.",
                reason="Not relevant.",
            ),
        }
    )
    sender = FakeSender()
    memory = JsonMemory(tmp_path / "state.json")

    result = Orchestrator([FakeTool([first, second, quiet])], llm, sender, memory).run()

    assert result.collected == 3
    assert result.considered == 3
    assert result.notified == 2
    assert len(sender.sent) == 1
    assert "2 game and Bengaluru alerts" in sender.sent[0][0]
    assert "Second alert" in sender.sent[0][1]
    assert "First alert" in sender.sent[0][1]
    assert "Quiet item" not in sender.sent[0][1]


def test_orchestrator_skips_events_older_than_max_age(tmp_path: Path) -> None:
    old_event = Event(
        id="old",
        source="test",
        title="Old game sale",
        summary="This sale is stale.",
        url="https://example.com/old",
        timestamp=datetime.now(timezone.utc) - timedelta(days=8),
    )
    fresh_event = Event(
        id="fresh",
        source="test",
        title="Fresh game sale",
        summary="This sale is current.",
        url="https://example.com/fresh",
        timestamp=datetime.now(timezone.utc),
    )
    llm = FakeLlm(
        NotificationDecision(
            notify=True,
            priority=8,
            subject="Fresh alert",
            body="This matters.",
            reason="Fresh and relevant.",
        )
    )
    sender = FakeSender()
    memory = JsonMemory(tmp_path / "state.json")

    result = Orchestrator(
        [FakeTool([old_event, fresh_event])],
        llm,
        sender,
        memory,
        max_event_age=timedelta(days=7),
    ).run()

    assert result.collected == 2
    assert result.considered == 1
    assert result.notified == 1
    assert result.skipped_old == 1
    assert llm.calls == 1
    assert len(sender.sent) == 1
    assert "Fresh game sale" in sender.sent[0][1]
    assert "Old game sale" not in sender.sent[0][1]


def test_orchestrator_continues_when_a_tool_fails(tmp_path: Path) -> None:
    event = make_event()
    llm = FakeLlm(
        NotificationDecision(
            notify=True,
            priority=8,
            subject="Worth knowing",
            body="This matters.",
            reason="It is relevant and timely.",
        )
    )
    sender = FakeSender()
    memory = JsonMemory(tmp_path / "state.json")

    result = Orchestrator([FailingTool(), FakeTool([event])], llm, sender, memory).run()

    assert result.collected == 1
    assert result.considered == 1
    assert result.notified == 1
    assert result.tool_errors == 1
    assert len(sender.sent) == 1


def test_orchestrator_skips_event_when_llm_fails(tmp_path: Path) -> None:
    event = make_event()
    llm = FailingLlm()
    sender = FakeSender()
    memory = JsonMemory(tmp_path / "state.json")

    result = Orchestrator([FakeTool([event])], llm, sender, memory).run()

    assert result.collected == 1
    assert result.considered == 1
    assert result.notified == 0
    assert result.decision_errors == 1
    assert sender.sent == []


def test_orchestrator_does_not_mark_notified_when_email_fails(tmp_path: Path) -> None:
    event = make_event()
    llm = FakeLlm(
        NotificationDecision(
            notify=True,
            priority=8,
            subject="Worth knowing",
            body="This matters.",
            reason="It is relevant and timely.",
        )
    )
    memory = JsonMemory(tmp_path / "state.json")

    result = Orchestrator([FakeTool([event])], llm, FailingSender(), memory).run()

    assert result.notified == 0
    assert result.notification_errors == 1

    reloaded = JsonMemory(tmp_path / "state.json")
    reloaded.load()
    assert not reloaded.has_notified(event.fingerprint)
