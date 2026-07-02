from pathlib import Path

import pytest

from okapi.agent import MODEL_ALIASES, detect_auth, resolve_model, resolve_paths


def test_aliases_resolve_to_full_ids():
    assert resolve_model("sonnet") == "claude-sonnet-5"
    assert resolve_model("opus") == "claude-opus-4-8"
    assert resolve_model("Haiku") == "claude-haiku-4-5"  # case-insensitive


def test_unknown_model_passes_through_untouched():
    assert resolve_model("claude-sonnet-4-6") == "claude-sonnet-4-6"
    assert resolve_model("claude-future-99") == "claude-future-99"


def test_default_model_is_a_known_alias():
    from okapi.agent import DEFAULT_MODEL
    assert DEFAULT_MODEL in MODEL_ALIASES


def test_detect_auth_prefers_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    assert detect_auth().mode == "api-key"


def test_detect_auth_falls_back_to_claude_code(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("okapi.agent.shutil.which", lambda _: "/usr/local/bin/claude")
    assert detect_auth().mode == "claude-code"


def test_detect_auth_errors_when_nothing_available(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("okapi.agent.shutil.which", lambda _: None)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    with pytest.raises(RuntimeError, match="no credentials"):
        detect_auth()


def test_resolve_paths_rejects_output_outside_root(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    with pytest.raises(ValueError, match="outside the analysis root"):
        resolve_paths(repo, tmp_path / "elsewhere")


def test_resolve_paths_defaults_output_to_repo_root(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    nested = repo / "src" / "pkg"
    nested.mkdir(parents=True)
    cwd, target, out = resolve_paths(nested, None)
    assert cwd == repo.resolve()
    assert out == repo.resolve() / "okf-knowledge"
