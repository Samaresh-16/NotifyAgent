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

    def decide_batch(self, events: list[Event]) -> list[NotificationDecision]:
        import httpx
        import json

        # Create a combined prompt for all events
        event_prompts = []
        for i, event in enumerate(events):
            event_prompts.append(f"Event {i+1}:\n{event_decision_prompt(event.to_prompt_payload())}")

        combined_prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"Evaluate each of the following events for an autonomous notification agent.\n"
            f"For each event, provide a notification decision in the same JSON format.\n"
            f"Return a JSON array with one decision object per event, in the same order as the events provided.\n\n"
            + "\n\n---\n\n".join(event_prompts)
        )

        # Create a schema for an array of decisions
        batch_schema = {
            "type": "array",
            "items": NotificationDecision.model_json_schema()
        }

        response = httpx.post(
            self._interactions_url(),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            },
            json={
                "model": self.model,
                "input": combined_prompt,
                "response_format": {
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": batch_schema,
                },
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()

        # Extract the array of decisions
        decisions_json = self._extract_text(response.json())
        decisions_list = json.loads(decisions_json)

        # Validate each decision
        return [NotificationDecision.model_validate(decision) for decision in decisions_list]

    # Note: This batch method is NOT used in the current fallback flow
    # (fallback uses individual decisions), but is retained for completeness
    # and potential future use if the orchestration logic changes.

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
                extracted = self._extract_json_from_text(item)
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


class NVIDIADecisionClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://integrate.api.nvidia.com/v1",
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

        # Try multiple endpoints in order of preference
        # Prioritize endpoints known to work with NVIDIA's API and have valid SSL certificates
        urls_to_try = [
            # User's configured endpoint (should be tried first)
            f"{self.base_url}/chat/completions",
            # NVIDIA's official AI endpoint (most likely to work based on documentation)
            "https://ai.api.nvidia.com/v1/chat/completions",
        ]
        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in urls_to_try:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

        last_error = None
        for url in unique_urls:
            try:
                response = httpx.post(
                    url,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}",
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"},
                    },
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                response_data = response.json()

                # Extract the text and parse it as a notification decision
                json_text = self._extract_text(response_data)
                decision = NotificationDecision.model_validate_json(json_text)

                # Validate that required string fields are not empty
                # If they are empty, provide sensible fallbacks based on the event
                if not decision.subject.strip():
                    decision.subject = f"Update from {event.source}"
                if not decision.body.strip():
                    decision.body = event.summary or f"Event from {event.source}"
                if not decision.reason.strip():
                    decision.reason = f"Automatically determined notification for {event.source} event"

                return decision
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404 or (500 <= e.response.status_code < 600):
                    last_error = e
                    continue  # Try next URL
                else:
                    # For non-404/5xx errors, don't try other URLs
                    raise
            except Exception as e:
                # For validation errors or other issues, try to create a fallback decision
                # rather than immediately failing, to reduce noise and improve reliability
                if "validation" in str(e).lower():
                    # Create a conservative fallback decision when validation fails
                    return NotificationDecision(
                        notify=False,
                        priority=1,
                        subject=f"Notification parsing issue for {event.source}",
                        body=f"Could not properly assess event: {event.title}",
                        reason="LLM response validation failed - using safe default"
                    )
                else:
                    # For non-validation errors (network, etc.), don't try other URLs
                    raise

        # If we exhausted all URLs and still have a 404 error, raise it
        if last_error:
            raise last_error
        # This shouldn't happen, but just in case
        raise RuntimeError("Failed to call NVIDIA API after trying all endpoints")

    def decide_batch(self, events: list[Event]) -> list[NotificationDecision]:
        import httpx
        import json

        # Create a combined prompt for all events
        event_prompts = []
        for i, event in enumerate(events):
            event_prompts.append(f"Event {i+1}:\n{event_decision_prompt(event.to_prompt_payload())}")

        combined_prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"Evaluate each of the following events for an autonomous notification agent.\n"
            f"For each event, provide a notification decision in the same JSON format.\n"
            f"Return a JSON array with one decision object per event, in the same order as the events provided.\n\n"
            + "\n\n---\n\n".join(event_prompts)
        )

        # Create a schema for an array of decisions
        batch_schema = {
            "type": "array",
            "items": NotificationDecision.model_json_schema()
        }

        # Try multiple endpoints in order of preference
        urls_to_try = [
            # User's configured endpoint (should be tried first)
            f"{self.base_url}/chat/completions",
            # NVIDIA's official AI endpoint (most likely to work based on documentation)
            "https://ai.api.nvidia.com/v1/chat/completions",
        ]
        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in urls_to_try:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

        last_error = None
        for url in unique_urls:
            try:
                response = httpx.post(
                    url,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}",
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "user", "content": combined_prompt}
                        ],
                        "temperature": 0.1,
                        "response_format": {
                            "type": "json_object",
                            "schema": batch_schema
                        },
                    },
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                response_data = response.json()

                # Extract the array of decisions
                decisions_json = self._extract_text(response_data)
                decisions_list = json.loads(decisions_json)

                # Validate each decision
                return [NotificationDecision.model_validate(decision) for decision in decisions_list]
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404 or (500 <= e.response.status_code < 600):
                    last_error = e
                    continue  # Try next URL
                else:
                    # For non-404/5xx errors, don't try other URLs
                    raise
            except Exception as e:
                # For validation errors or other issues, try to create fallback decisions
                # rather than immediately failing, to reduce noise and improve reliability
                if "validation" in str(e).lower():
                    # Create conservative fallback decisions when validation fails
                    return [
                        NotificationDecision(
                            notify=False,
                            priority=1,
                            subject=f"Notification parsing issue for {event.source}",
                            body=f"Could not properly assess event: {event.title}",
                            reason="LLM response validation failed - using safe default"
                        )
                        for event in events
                    ]
                else:
                    # For non-validation errors (network, etc.), don't try other URLs
                    raise

        # If we exhausted all URLs and still have a 404 error, raise it
        if last_error:
            raise last_error
        # This shouldn't happen, but just in case
        raise RuntimeError("Failed to call NVIDIA API after trying all endpoints")

    def _extract_text(self, payload: dict[str, Any]) -> str:
        """Extract text from Gemini/NVIDIA response payload."""
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
        raise ValueError(f"NVIDIA response did not contain a notification decision. Top-level keys: {keys}")

    def _find_decision_payload(self, value: Any) -> dict[str, Any] | None:
        """Find notification decision payload in nested dict/list structures."""
        if isinstance(value, dict):
            if _looks_like_decision(value):
                # Validate that it matches the expected schema
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
        """Recursively search for JSON text in nested structures."""
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
        """Extract JSON from text, handling markdown code fences."""
        if not isinstance(value, str) or not value.strip():
            return None

        stripped = _strip_json_fence(value.strip())
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return None

        # Validate that it looks like a decision
        if _looks_like_decision(parsed):
            # Validate against the schema
            NotificationDecision.model_validate(parsed)
            return json.dumps(parsed)

        return None


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


GeminiDecisionClient._interactions_url = lambda self: f"{self.base_url}/interactions"