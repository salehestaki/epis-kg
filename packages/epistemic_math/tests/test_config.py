import json

from epistemic_math.config import load_params


def test_defaults(monkeypatch, tmp_path):
    for k in ("EPIS_ALPHA", "EPIS_BETA", "EPIS_GAMMA", "EPIS_LAMBDA"):
        monkeypatch.delenv(k, raising=False)
    # Point at a non-existent tuned file so we test the true built-in defaults
    # regardless of whether a tuned_params.json is shipped in the package.
    monkeypatch.setenv("EPIS_TUNED_PARAMS", str(tmp_path / "none.json"))
    p = load_params()
    assert p.alpha == 0.5 and p.beta == 0.35 and p.gamma == 0.15


def test_env_overrides_defaults(monkeypatch):
    monkeypatch.setenv("EPIS_ALPHA", "0.9")
    monkeypatch.delenv("EPIS_TUNED_PARAMS", raising=False)
    assert load_params().alpha == 0.9


def test_tuned_file_loaded_and_env_wins(tmp_path, monkeypatch):
    tuned = tmp_path / "tuned_params.json"
    tuned.write_text(json.dumps({"alpha": 0.11, "beta": 0.22, "pearson_r": 0.7}))
    monkeypatch.setenv("EPIS_TUNED_PARAMS", str(tuned))
    monkeypatch.delenv("EPIS_ALPHA", raising=False)
    monkeypatch.delenv("EPIS_BETA", raising=False)

    p = load_params()
    assert p.alpha == 0.11  # from tuned file
    assert p.beta == 0.22

    # env still takes precedence over the tuned file
    monkeypatch.setenv("EPIS_ALPHA", "0.99")
    assert load_params().alpha == 0.99
