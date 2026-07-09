from llm.client import GeminiDecisionClient


def test_gemini_client_extracts_direct_structured_payload() -> None:
    client = GeminiDecisionClient(
        api_key="key",
        model="gemini-3.5-flash",
    )

    text = client._extract_text(
        {
            "notify": True,
            "priority": 8,
            "subject": "Worth knowing",
            "body": "This matters.",
            "reason": "It is relevant and timely.",
        }
    )

    assert '"notify": true' in text


def test_gemini_client_extracts_candidate_text() -> None:
    client = GeminiDecisionClient(
        api_key="key",
        model="gemini-3.5-flash",
    )

    text = client._extract_text(
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": '{"notify": true, "priority": 8, "subject": "A", "body": "B", "reason": "C"}'
                            }
                        ]
                    }
                }
            ]
        }
    )

    assert '"notify": true' in text


def test_gemini_client_extracts_interactions_output_text() -> None:
    client = GeminiDecisionClient(
        api_key="key",
        model="gemini-3.5-flash",
    )

    text = client._extract_text(
        {
            "id": "v1_example",
            "model": "gemini-3.5-flash",
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": '{"notify": false, "priority": 2, "subject": "No alert", "body": "Not important.", "reason": "Low relevance."}',
                        }
                    ]
                }
            ],
        }
    )

    assert '"notify": false' in text


def test_gemini_client_extracts_nested_structured_payload() -> None:
    client = GeminiDecisionClient(
        api_key="key",
        model="gemini-3.5-flash",
    )

    text = client._extract_text(
        {
            "id": "v1_example",
            "model": "gemini-3.5-flash",
            "output": [
                {
                    "content": [
                        {
                            "json": {
                                "notify": True,
                                "priority": 8,
                                "subject": "Alert",
                                "body": "This matters.",
                                "reason": "Relevant to Bengaluru.",
                            }
                        }
                    ]
                }
            ],
        }
    )

    assert '"notify": true' in text
