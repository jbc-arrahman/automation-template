"""All settings in one place, read from the environment / `.env`.

Every value has a safe default, so `Settings()` works with only an API key set. CLI flags override
these per run (see app/cli.py). Add your own settings here as plain fields + one line in
`from_env()` - nothing else needs to change.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=False)

# Keep browser-use quiet and private unless the user opts in.
os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")
os.environ.setdefault("BROWSER_USE_SETUP_LOGGING", "false")
# Local DevTools (CDP) calls must never go through an HTTP(S)_PROXY from the environment.
os.environ["NO_PROXY"] = ",".join(filter(None, [os.environ.get("NO_PROXY", ""), "127.0.0.1", "localhost"]))
os.environ["no_proxy"] = os.environ["NO_PROXY"]


def _bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None or v.strip() == "":
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    v = os.getenv(name, "").strip()
    return int(v) if v else default


def _float(name: str, default: float) -> float:
    v = os.getenv(name, "").strip()
    return float(v) if v else default


def _str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _list(name: str) -> List[str]:
    return [x.strip() for x in os.getenv(name, "").split(",") if x.strip()]


def _path(name: str, default: str) -> Path:
    p = Path(os.path.expanduser(_str(name, default)))
    return p if p.is_absolute() else PROJECT_ROOT / p


@dataclass
class Settings:
    # ---- LLM ---------------------------------------------------------------------------------
    llm_provider: str = "google"            # google | openai | anthropic | azure | groq | ollama | ...
    llm_model: str = ""                     # empty -> provider default (see app/llm.py)
    llm_api_key: str = ""                   # empty -> provider's own env var (GEMINI_API_KEY, ...)
    llm_base_url: str = ""                  # OpenAI-compatible endpoints / Ollama host
    llm_temperature: Optional[float] = None
    use_vision: bool = True

    # ---- Browser -----------------------------------------------------------------------------
    browser_mode: str = "fresh"             # installed | fresh
    # Mode 1 (installed)
    installed_action: str = "launch"        # launch | attach
    chrome_binary: str = ""                 # empty -> auto-detect per OS
    chrome_user_data_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "profiles" / "installed")
    chrome_profile_directory: str = "Default"
    cdp_host: str = "127.0.0.1"
    cdp_port: int = 9222
    cdp_url: str = ""                       # full override, e.g. http://host.docker.internal:9222
    close_installed_on_exit: bool = False   # Mode 1 keeps Chrome open between runs by default
    # Mode 2 (fresh)
    headless: bool = False
    fresh_profile: str = "ephemeral"        # ephemeral | persistent
    fresh_profile_name: str = "default"
    profiles_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "profiles")
    fresh_executable_path: str = ""         # empty -> browser-use's managed Chromium
    # Both modes
    window_width: int = 1366
    window_height: int = 900
    allowed_domains: List[str] = field(default_factory=list)  # empty -> task's own list / no limit
    wait_between_actions: float = 0.5
    extra_chrome_args: List[str] = field(default_factory=list)

    # ---- Agent -------------------------------------------------------------------------------
    max_steps: int = 25
    task_timeout_sec: int = 360
    max_failures: int = 3

    # ---- Cost / logs -------------------------------------------------------------------------
    max_daily_llm_cost: float = 0.0         # USD, 0 = no cap
    logs_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "logs")
    trace_enabled: bool = True
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Settings":
        d = cls()
        temp = _str("LLM_TEMPERATURE")
        return cls(
            llm_provider=_str("LLM_PROVIDER", d.llm_provider).lower(),
            llm_model=_str("LLM_MODEL"),
            llm_api_key=_str("LLM_API_KEY"),
            llm_base_url=_str("LLM_BASE_URL"),
            llm_temperature=float(temp) if temp else None,
            use_vision=_bool("USE_VISION", d.use_vision),
            browser_mode=_str("BROWSER_MODE", d.browser_mode).lower(),
            installed_action=_str("INSTALLED_ACTION", d.installed_action).lower(),
            chrome_binary=_str("CHROME_BINARY"),
            chrome_user_data_dir=_path("CHROME_USER_DATA_DIR", str(d.chrome_user_data_dir)),
            chrome_profile_directory=_str("CHROME_PROFILE_DIRECTORY", d.chrome_profile_directory),
            cdp_host=_str("CDP_HOST", d.cdp_host),
            cdp_port=_int("CDP_PORT", d.cdp_port),
            cdp_url=_str("CDP_URL"),
            close_installed_on_exit=_bool("CLOSE_INSTALLED_ON_EXIT", d.close_installed_on_exit),
            headless=_bool("HEADLESS", d.headless),
            fresh_profile=_str("FRESH_PROFILE", d.fresh_profile).lower(),
            fresh_profile_name=_str("FRESH_PROFILE_NAME", d.fresh_profile_name),
            profiles_dir=_path("PROFILES_DIR", str(d.profiles_dir)),
            fresh_executable_path=_str("FRESH_EXECUTABLE_PATH"),
            window_width=_int("WINDOW_WIDTH", d.window_width),
            window_height=_int("WINDOW_HEIGHT", d.window_height),
            allowed_domains=_list("ALLOWED_DOMAINS"),
            wait_between_actions=_float("WAIT_BETWEEN_ACTIONS", d.wait_between_actions),
            extra_chrome_args=_list("EXTRA_CHROME_ARGS"),
            max_steps=_int("AGENT_MAX_STEPS", d.max_steps),
            task_timeout_sec=_int("AGENT_TASK_TIMEOUT_SEC", d.task_timeout_sec),
            max_failures=_int("AGENT_MAX_FAILURES", d.max_failures),
            max_daily_llm_cost=_float("MAX_DAILY_LLM_COST", d.max_daily_llm_cost),
            logs_dir=_path("LOGS_DIR", str(d.logs_dir)),
            trace_enabled=_bool("TRACE_ENABLED", d.trace_enabled),
            log_level=_str("LOG_LEVEL", d.log_level).upper(),
        )

    @property
    def resolved_cdp_url(self) -> str:
        return self.cdp_url or f"http://{self.cdp_host}:{self.cdp_port}"
