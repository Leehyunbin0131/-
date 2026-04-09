from __future__ import annotations

from app.config import Settings
from app.llm.ollama_util import ollama_base_url_for_settings


def test_ollama_base_url_default(monkeypatch) -> None:
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    s = Settings(ollama_host=None)
    assert ollama_base_url_for_settings(s) == "http://127.0.0.1:11434"


def test_ollama_base_url_explicit() -> None:
    s = Settings(ollama_host="http://192.168.1.5:11434")
    assert ollama_base_url_for_settings(s) == "http://192.168.1.5:11434"


def test_ollama_base_url_maps_bind_all_to_loopback(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_HOST", "0.0.0.0:11434")
    s = Settings(ollama_host=None)
    assert ollama_base_url_for_settings(s) == "http://127.0.0.1:11434"
