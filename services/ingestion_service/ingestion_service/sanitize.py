"""Text sanitisation and deterministic id generation."""

from __future__ import annotations

import hashlib
import re
import unicodedata

_WHITESPACE = re.compile(r"\s+")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_URL = re.compile(r"https?://\S+")


def sanitize(text: str) -> str:
    """Normalise unicode, strip control chars, and collapse whitespace."""
    text = unicodedata.normalize("NFKC", text)
    text = _CONTROL.sub(" ", text)
    text = _WHITESPACE.sub(" ", text)
    return text.strip()


def content_id(content: str, url: str | None = None) -> str:
    """Deterministic id from url+content so re-ingestion is idempotent."""
    h = hashlib.sha256()
    h.update((url or "").encode("utf-8"))
    h.update(b"\x00")
    h.update(content.encode("utf-8"))
    return "doc_" + h.hexdigest()[:16]


def extract_urls(text: str) -> list[str]:
    """Return URLs mentioned in the text (candidate evidence references)."""
    return _URL.findall(text)
