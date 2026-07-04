"""Standalone connectivity test for the DeepSeek OpenAI-compatible proxy.

Usage:
    # 1. put your key in the environment (see below), then:
    python scripts/test_deepseek_connection.py

Reads DEEPSEEK_API_KEY and DEEPSEEK_BASE_URL (default the tapsage proxy) and
sends a tiny chat request to `deepseek-v4-flash`, printing the answer plus any
reasoning/thinking trace the model returns.

Where to put your key (pick one):
  * Preferred: add it to the repo's `.env` file (which is git-ignored):
        DEEPSEEK_API_KEY=sk-...
    then load it, e.g.  `set -a; source .env; set +a`  (bash)
    or on PowerShell:   `$env:DEEPSEEK_API_KEY="sk-..."`
  * Or export it inline for one run:
        DEEPSEEK_API_KEY=sk-... python scripts/test_deepseek_connection.py
Never commit the key or paste it into source files.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _load_dotenv() -> None:
    """Load the repo's .env (KEY=VALUE lines) so pasting the key there is enough.

    Only sets variables that aren't already in the environment; ignores comments.
    """
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv()

BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.gapgpt.app/v1")
MODEL = os.getenv("LLM_MODEL", "deepseek-v4-flash")
USE_REASONING = os.getenv("EPIS_REASONING_PARAMS", "true").lower() in ("1", "true", "yes")

REASONING_EXTRA = {"thinking": {"type": "enabled"}, "reasoning_effort": "high"}


def main() -> int:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("ERROR: DEEPSEEK_API_KEY is not set. See the docstring for where to put it.")
        return 2

    try:
        from openai import OpenAI
    except ImportError:
        print("ERROR: the `openai` package is not installed. Run: pip install openai")
        return 2

    client = OpenAI(api_key=api_key, base_url=BASE_URL)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello! Test connection."},
    ]

    print(f"→ Endpoint : {BASE_URL}")
    print(f"→ Model    : {MODEL}")
    print(f"→ Reasoning params: {'on' if USE_REASONING else 'off'}\n")

    def _call(extra_body):  # noqa: ANN001
        return client.chat.completions.create(
            model=MODEL, messages=messages, extra_body=extra_body or None
        )

    try:
        resp = _call(REASONING_EXTRA if USE_REASONING else None)
    except Exception as exc:  # noqa: BLE001
        # The reasoning kwargs may be rejected by the endpoint — retry plain.
        print(f"! First call failed ({exc}).")
        if USE_REASONING:
            print("! Retrying without reasoning params...\n")
            try:
                resp = _call(None)
            except Exception as exc2:  # noqa: BLE001
                print(f"ERROR: connection failed: {exc2}")
                return 1
        else:
            print(f"ERROR: connection failed: {exc}")
            return 1

    msg = resp.choices[0].message
    print("=== ANSWER ===")
    print(msg.content or "(empty)")

    # DeepSeek reasoning models expose the chain-of-thought in reasoning_content.
    reasoning = getattr(msg, "reasoning_content", None) or getattr(msg, "reasoning", None)
    if reasoning:
        print("\n=== REASONING / THINKING ===")
        print(reasoning)
    else:
        print("\n(no separate reasoning trace returned by the endpoint)")

    usage = getattr(resp, "usage", None)
    if usage:
        print(f"\n=== USAGE ===\n{usage}")
    print("\n✓ Connection OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
