from __future__ import annotations

from app.chat.models import CounselingSummary
from app.llm.base import ChatMessage
from app.llm.providers.ollama_provider import OllamaProvider


def test_ollama_responses_parse_validates_counseling_summary(monkeypatch) -> None:
    json_out = (
        '{"overview":"o","recommended_options":[],"next_actions":[],"closing_message":"c"}'
    )

    class _Msg:
        content = json_out

    class _Resp:
        message = _Msg()

    class _FakeClient:
        def chat(self, **kwargs):  # noqa: ANN003, ANN002
            return _Resp()

    monkeypatch.setattr(
        "app.llm.providers.ollama_provider.ollama.Client",
        lambda **kw: _FakeClient(),
    )

    provider = OllamaProvider(
        chat_model="gemma3:4b",
        embed_model="nomic-embed-text",
        host=None,
        timeout_seconds=1.0,
        chat_temperature=0.2,
    )
    gen = provider.responses_parse(
        [ChatMessage(role="user", content="{}")],
        text_format=CounselingSummary,
    )
    assert gen.parsed is not None
    assert gen.parsed["overview"] == "o"
    assert gen.parsed["closing_message"] == "c"


def test_ollama_responses_create_returns_text(monkeypatch) -> None:
    class _Msg:
        content = "  hello  "

    class _Resp:
        message = _Msg()

    class _FakeClient:
        def chat(self, **kwargs):  # noqa: ANN003, ANN002
            return _Resp()

    monkeypatch.setattr(
        "app.llm.providers.ollama_provider.ollama.Client",
        lambda **kw: _FakeClient(),
    )

    provider = OllamaProvider(
        chat_model="gemma3:4b",
        embed_model="nomic-embed-text",
        host=None,
        timeout_seconds=1.0,
        chat_temperature=0.2,
    )
    gen = provider.responses_create([ChatMessage(role="user", content="q")])
    assert gen.content == "hello"
