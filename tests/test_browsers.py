"""Both browser modes start, navigate and stop - real browser, NO LLM call.

    make test-browser        (or: uv run pytest -m browser)
"""
import socket
from dataclasses import replace

import pytest

from app.browser import cdp, installed, open_browser
from app.config import Settings

pytestmark = pytest.mark.browser

PAGE = "data:text/html,<title>bub-ok</title><h1>hello</h1>"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def _navigate_and_title(browser) -> str:
    await browser.start()
    await browser.navigate_to(PAGE)
    page = await browser.get_current_page()
    return await page.evaluate("() => document.title")


async def test_fresh_mode_ephemeral(tmp_path):
    s = replace(Settings.from_env(), headless=True, fresh_profile="ephemeral", logs_dir=tmp_path)
    handle = open_browser(s, "fresh")
    try:
        assert await _navigate_and_title(handle.browser) == "bub-ok"
    finally:
        await handle.close()
    assert not handle.temp_profile.exists()


async def test_fresh_mode_persistent_keeps_profile(tmp_path):
    s = replace(Settings.from_env(), headless=True, fresh_profile="persistent",
                profiles_dir=tmp_path, fresh_profile_name="t")
    handle = open_browser(s, "fresh")
    try:
        await _navigate_and_title(handle.browser)
    finally:
        await handle.close()
    assert (tmp_path / "fresh" / "t").is_dir()


async def test_installed_mode_launch_reuse_close(tmp_path):
    try:
        installed.find_chrome_binary()
    except FileNotFoundError:
        pytest.skip("Google Chrome not installed")
    port = _free_port()
    s = replace(Settings.from_env(), headless=True, installed_action="launch", cdp_port=port,
                cdp_host="127.0.0.1", cdp_url="", chrome_user_data_dir=tmp_path / "udd",
                close_installed_on_exit=False)
    handle = open_browser(s, "installed")
    try:
        assert await _navigate_and_title(handle.browser) == "bub-ok"
    finally:
        await handle.close()
    # keep_alive: Chrome must still be running after the run ...
    assert cdp.is_ready(s.resolved_cdp_url)
    # ... and a second run re-uses it
    handle2 = open_browser(s, "installed")
    await handle2.close()
    assert installed.close_chrome(s)


def test_websocket_url_rewrites_host(monkeypatch):
    monkeypatch.setattr(cdp, "version", lambda url, timeout=2.0: {
        "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/browser/abc"})
    monkeypatch.setattr(cdp.socket, "gethostbyname", lambda h: "192.168.65.254")
    assert cdp.websocket_url("http://host.docker.internal:9222") == \
        "ws://192.168.65.254:9222/devtools/browser/abc"
