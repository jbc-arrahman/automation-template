"""Browser factory: `open_browser(settings, mode)` -> a BrowserHandle for either mode.

    handle = open_browser(settings, allowed_domains=["example.com"])
    agent = Agent(..., browser=handle.browser)
    ...
    await handle.close()      # Mode 1: leaves Chrome running (unless CLOSE_INSTALLED_ON_EXIT)
                              # Mode 2: kills the browser and deletes an ephemeral profile
"""
from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from browser_use import Browser

from app.browser import cdp, installed
from app.browser.fresh import build_fresh_browser
from app.config import Settings

log = logging.getLogger(__name__)

MODES = ("installed", "fresh")


@dataclass
class BrowserHandle:
    browser: Browser
    mode: str
    settings: Settings
    temp_profile: Optional[Path] = None

    async def close(self) -> None:
        if self.mode == "installed":
            # keep_alive=True: browser-use only disconnects; Chrome keeps running for the next run.
            if self.settings.close_installed_on_exit:
                try:
                    await self.browser.kill()
                except Exception:
                    pass
                installed.close_chrome(self.settings)
            return
        try:
            await self.browser.kill()
        except Exception as e:
            log.debug("browser.kill(): %s", e)
        if self.temp_profile and self.settings.fresh_profile == "ephemeral":
            shutil.rmtree(self.temp_profile, ignore_errors=True)


def open_browser(settings: Settings, mode: Optional[str] = None,
                 allowed_domains: Optional[list[str]] = None) -> BrowserHandle:
    mode = (mode or settings.browser_mode).lower()
    domains = settings.allowed_domains or allowed_domains or None

    if mode == "installed":
        url = installed.ensure_chrome(settings)
        browser = Browser(
            cdp_url=cdp.websocket_url(url),
            keep_alive=True,
            allowed_domains=domains,
            wait_between_actions=settings.wait_between_actions,
        )
        return BrowserHandle(browser, mode, settings)

    if mode == "fresh":
        browser, profile = build_fresh_browser(settings, domains)
        return BrowserHandle(browser, mode, settings, temp_profile=profile)

    raise ValueError(f"Unknown browser mode '{mode}'. Use one of: {', '.join(MODES)}")
