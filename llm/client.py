from __future__ import annotations

import json
from typing import Any

from agent.models import Event, NotificationDecision
from llm.prompts import SYSTEM_PROMPT, event_decision_prompt


class GeminiDecisionClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        timeout_seconds: float = 60.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def decide(self, event: Event) -> NotificationDecision:
        import httpx

        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"{event_decision_prompt(event.to_prompt_payload())}"
        )
        response = httpx.post(
            self._interactions_url(),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
            json={
                "model": self.model,
                "input": prompt,
                "response_format": {
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": NotificationDecision.model_json_schema(),
                },
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return NotificationDecision.model_validate_json(
            self._extract_text(response.json())
        )

    def _interactions_url(self) -> str:
        return f"{self.base_url}/interactions"

    def _extract_text(self, payload: dict[str, Any]) -> str:
        decision_payload = self._find_decision_payload(payload)
        if decision_payload is not None:
            return json.dumps(decision_payload)

        for key in ("output_text", "outputText", "text", "content"):
            value = payload.get(key)
            extracted = self._extract_json_from_text(value)
            if extracted is not None:
                return extracted

        candidates = payload.get("candidates")
        if candidates:
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            text_parts = [
                part["text"]
                for part in parts
                if isinstance(part, dict) and isinstance(part.get("text"), str)
            ]
            if text_parts:
                extracted = self._extract_json_from_text("\n".join(text_parts))
                if extracted is not None:
                    return extracted

        extracted = self._find_json_text(payload)
        if extracted is not None:
            return extracted

        keys = ", ".join(sorted(payload.keys()))
        raise ValueError(f"Gemini response did not contain a notification decision. Top-level keys: {keys}")

    def _find_decision_payload(self, value: Any) -> dict[str, Any] | None:
        if isinstance(value, dict):
            if _looks_like_decision(value):
                NotificationDecision.model_validate(value)
                return value

            for child in value.values():
                found = self._find_decision_payload(child)
                if found is not None:
                    return found

        if isinstance(value, list):
            for item in value:
                found = self._find_decision_payload(item)
                if found is not None:
                    return found

        return None

    def _find_json_text(self, value: Any) -> str | None:
        if isinstance(value, str):
            return self._extract_json_from_text(value)

        if isinstance(value, dict):
            for key in ("text", "output_text", "outputText", "content"):
                extracted = self._extract_json_from_text(value.get(key))
                if extracted is not None:
                    return extracted
            for child in value.values():
                extracted = self._find_json_text(child)
                if extracted is not None:
                    return extracted

        if isinstance(value, list):
            for item in value:
                extracted = self._find_json_text(item)
                if extracted is not None:
                    return extracted

        return None

    def _extract_json_from_text(self, value: Any) -> str | None:
        if not isinstance(value, str) or not value.strip():
            return None

        stripped = _strip_json_fence(value.strip())
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return None

        NotificationDecision.model_validate(parsed)
        return json.dumps(parsed)


def _looks_like_decision(value: dict[str, Any]) -> bool:
    return {"notify", "priority", "subject", "body", "reason"}.issubset(value.keys())


def _strip_json_fence(value: str) -> str:
    if not value.startswith("```"):
        return value

    lines = value.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()
