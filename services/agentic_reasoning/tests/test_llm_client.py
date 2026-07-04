from agentic_reasoning.llm_client import ChatSettings, _default_model, _extract_json


def test_default_provider_is_deepseek(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    cfg = ChatSettings.from_env()
    assert cfg.provider == "deepseek"
    assert cfg.model == "deepseek-v4-flash"


def test_model_default_follows_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    assert ChatSettings.from_env().model == _default_model("openai")


def test_explicit_model_overrides(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("LLM_MODEL", "deepseek-custom")
    assert ChatSettings.from_env().model == "deepseek-custom"


def test_extract_json_from_reasoning_wrapped_output():
    # Reasoning models may prepend a thinking preamble before the JSON answer.
    raw = 'Let me think... the claim is atomic.\n{"claims": [{"id": "c1"}]}'
    assert _extract_json(raw) == {"claims": [{"id": "c1"}]}


def test_extract_json_from_code_fence():
    raw = '```json\n{"ok": true}\n```'
    assert _extract_json(raw) == {"ok": True}
