from pathlib import Path

from agent.memory import JsonMemory


def test_json_memory_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    memory = JsonMemory(path)

    memory.load()
    memory.mark_notified("abc")
    memory.save()

    reloaded = JsonMemory(path)
    reloaded.load()

    assert reloaded.has_notified("abc")

