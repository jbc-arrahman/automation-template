"""Mode 2 - a completely NEW browser instance, started and owned by browser-use.

browser-use launches Chromium itself (its managed Playwright Chromium if installed - `make
install-browser` - otherwise a Chrome/Chromium it finds on the device) and kills it after the run.

FRESH_PROFILE:
  ephemeral   brand-new temp profile every run, deleted afterwards. Clean, no cookies, nothing kept.
  persistent  isolated profile in PROFILES_DIR/fresh/<FRESH_PROFILE_NAME>. Logins and cookies
              survive between runs, but it never touches your everyday Chrome.
"""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from browser_use import Browser

from app.config import Settings

log = logging.getLogger(__name__)


def fresh_profile_dir(settings: Settings) -> Path:
    if settings.fresh_profile == "persistent":
        p = settings.profiles_dir / "fresh" / settings.fresh_profile_name
        p.mkdir(parents=True, exist_ok=True)
        return p
    # browser-use treats dirs containing this prefix as temp dirs (it won't copy them again).
    return Path(tempfile.mkdtemp(prefix="browser-use-user-data-dir-"))


def build_fresh_browser(settings: Settings, allowed_domains: list[str] | None) -> tuple[Browser, Path]:
    user_data_dir = fresh_profile_dir(settings)
    kwargs = dict(
        headless=settings.headless,
        user_data_dir=str(user_data_dir),
        window_size={"width": settings.window_width, "height": settings.window_height},
        allowed_domains=allowed_domains or None,
        wait_between_actions=settings.wait_between_actions,
        args=list(settings.extra_chrome_args),
        keep_alive=False,
    )
    if settings.fresh_executable_path:
        kwargs["executable_path"] = settings.fresh_executable_path
    log.info("Starting a fresh browser (%s profile, headless=%s) at %s",
             settings.fresh_profile, settings.headless, user_data_dir)
    return Browser(**kwargs), user_data_dir
