"""Config, LLM factory and task registry - fast, no browser, no network."""
import pytest

from app.config import Settings
from app.llm import PROVIDERS, LLMConfigError, build_llm
from app.tasks import BaseTask, TaskInputError, all_tasks, get_task


def test_settings_defaults(monkeypatch):
    for k in ("BROWSER_MODE", "CDP_PORT", "CDP_URL", "LLM_PROVIDER"):
        monkeypatch.delenv(k, raising=False)
    s = Settings.from_env()
    assert s.browser_mode == "fresh"
    assert s.resolved_cdp_url == "http://127.0.0.1:9222"
    assert s.llm_provider == "google"


def test_settings_env_override(monkeypatch):
    monkeypatch.setenv("BROWSER_MODE", "installed")
    monkeypatch.setenv("CDP_PORT", "9333")
    monkeypatch.setenv("ALLOWED_DOMAINS", "a.com, b.com")
    s = Settings.from_env()
    assert s.browser_mode == "installed"
    assert s.resolved_cdp_url.endswith(":9333")
    assert s.allowed_domains == ["a.com", "b.com"]


def test_llm_missing_key_is_clear(monkeypatch):
    for k in ("LLM_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "google")
    with pytest.raises(LLMConfigError, match="GEMINI_API_KEY"):
        build_llm(Settings.from_env())


def test_llm_unknown_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "nope")
    with pytest.raises(LLMConfigError):
        build_llm(Settings.from_env())


@pytest.mark.parametrize("provider", ["google", "openai", "anthropic", "groq", "openrouter", "deepseek"])
def test_llm_builds_offline(monkeypatch, provider):
    monkeypatch.setenv("LLM_PROVIDER", provider)
    monkeypatch.setenv("LLM_API_KEY", "dummy")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    llm = build_llm(Settings.from_env())
    assert llm.model == PROVIDERS[provider].default_model


def test_registry_finds_examples():
    names = all_tasks()
    assert {"hn_top_stories", "httpbin_form", "prompt"} <= set(names)


def test_required_inputs_enforced():
    with pytest.raises(TaskInputError):
        get_task("httpbin_form")()
    t = get_task("httpbin_form")(customer="Jane")
    assert "Jane" in t.prompt() and t.inputs["size"] == "medium"


def test_prompts_render():
    for cls in all_tasks().values():
        inputs = {k: "x" for k in cls.required_inputs}
        assert isinstance(cls(**inputs).prompt(), str)


def test_sensitive_env(monkeypatch):
    class T(BaseTask):
        name = "t"
        sensitive_env = {"x_password": "MY_PASS"}

        def prompt(self):
            return "type x_password"

    monkeypatch.setenv("MY_PASS", "s3cret")
    assert T().sensitive_data() == {"x_password": "s3cret"}
