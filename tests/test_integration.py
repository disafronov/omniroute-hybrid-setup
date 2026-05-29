"""Integration smoke tests — require running OmniRoute + Ollama."""

import json
import os
import urllib.request

import pytest

pytestmark = pytest.mark.integration

LOCAL_URL = os.environ.get("LOCAL_BASE_URL", "http://127.0.0.1:20128")
LOCAL_API_KEY = os.environ.get("LOCAL_API_KEY")

LOCAL_FAST = os.environ.get("LOCAL_FAST", "qwen3.5:4b-q8_0")
LOCAL_CODING = os.environ.get("LOCAL_CODING", "qwen3.5:9b-q4_K_M")


@pytest.fixture
def headers():
    assert LOCAL_API_KEY, "LOCAL_API_KEY must be set"
    return {
        "Authorization": f"Bearer {LOCAL_API_KEY}",
        "Content-Type": "application/json",
    }


def _request(body: dict, headers: dict) -> urllib.request.Request:
    return urllib.request.Request(
        f"{LOCAL_URL}/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers=headers,
        method="POST",
    )


class TestNonStreaming:
    def test_fast_model_returns_content(self, headers):
        req = _request(
            {
                "model": f"local_ollama/{LOCAL_FAST}",
                "messages": [{"role": "user", "content": "say hi in 2 words"}],
                "stream": False,
            },
            headers,
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())

        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        assert content, "empty content in non-streaming response"

    def test_coding_model_returns_content(self, headers):
        req = _request(
            {
                "model": f"local_ollama/{LOCAL_CODING}",
                "messages": [{"role": "user", "content": "say hi in 2 words"}],
                "stream": False,
            },
            headers,
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())

        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        assert content, "empty content in non-streaming response"


class TestStreaming:
    def test_fast_model_streams_first_chunk(self, headers):
        req = _request(
            {
                "model": f"local_ollama/{LOCAL_FAST}",
                "messages": [{"role": "user", "content": "say hi in 2 words"}],
                "stream": True,
            },
            headers,
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            first_line = resp.readline().decode().strip()

        assert first_line.startswith(
            "data: "
        ), f"expected SSE data line, got: {first_line[:80]}"
        payload = json.loads(first_line.removeprefix("data: "))
        assert "choices" in payload, "first SSE chunk missing choices"

    def test_coding_model_streams_first_chunk(self, headers):
        req = _request(
            {
                "model": f"local_ollama/{LOCAL_CODING}",
                "messages": [{"role": "user", "content": "say hi in 2 words"}],
                "stream": True,
            },
            headers,
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            first_line = resp.readline().decode().strip()

        assert first_line.startswith(
            "data: "
        ), f"expected SSE data line, got: {first_line[:80]}"
        payload = json.loads(first_line.removeprefix("data: "))
        assert "choices" in payload, "first SSE chunk missing choices"
