"""Helpers for Ollama base URL (matches ollama-python host resolution)."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from app.config import Settings


def _loopback_if_all_interfaces(url: str) -> str:
    """OLLAMA_HOST=0.0.0.0 is a bind address; HTTP clients must use loopback."""
    parsed = urlparse(url)
    host = parsed.hostname
    if host not in ("0.0.0.0", "::", None):
        return url.rstrip("/")
    scheme = parsed.scheme or "http"
    if parsed.port:
        return f"{scheme}://127.0.0.1:{parsed.port}".rstrip("/")
    return f"{scheme}://127.0.0.1".rstrip("/")


def ollama_base_url_for_settings(settings: Settings) -> str:
    """Effective API base URL for HTTP checks and ollama.Client(host=...) (no trailing slash)."""
    from ollama._client import _parse_host

    raw = (settings.ollama_host or "").strip() or (os.getenv("OLLAMA_HOST") or "").strip() or None
    url = _parse_host(raw).rstrip("/")
    return _loopback_if_all_interfaces(url)
