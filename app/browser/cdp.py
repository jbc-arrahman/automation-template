"""Tiny DevTools (CDP) HTTP helpers - only the /json/* endpoints, no websocket client.

Used by Mode 1 to check whether a Chrome is listening, and to turn an http:// CDP address into the
browser's ws:// URL in a form that also works from inside Docker:

Chrome refuses DevTools HTTP requests whose Host header is not `localhost` or an IP address, and
the ws URL it returns always says 127.0.0.1. So when the host is a name such as
`host.docker.internal`, we resolve it to an IP first and rewrite the returned ws URL to that IP.
"""
from __future__ import annotations

import json
import socket
import urllib.request
from typing import Optional
from urllib.parse import urlparse, urlunparse

# Never send local DevTools calls through an HTTP(S)_PROXY from the environment.
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _get_json(url: str, timeout: float = 2.0):
    with _opener.open(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _ip_url(http_url: str) -> str:
    """http://name:port -> http://<ip>:port (Chrome rejects non-IP Host headers)."""
    p = urlparse(http_url)
    host = p.hostname or "127.0.0.1"
    if host != "localhost":
        try:
            host = socket.gethostbyname(host)
        except OSError:
            pass
    return urlunparse(p._replace(netloc=f"{host}:{p.port or 9222}"))


def version(http_url: str, timeout: float = 2.0) -> Optional[dict]:
    """The /json/version document, or None if nothing answers."""
    try:
        return _get_json(_ip_url(http_url).rstrip("/") + "/json/version", timeout)
    except Exception:
        return None


def is_ready(http_url: str) -> bool:
    return version(http_url) is not None


def websocket_url(cdp_url: str) -> str:
    """Return a ws:// URL reachable from this process. ws:// input is returned unchanged."""
    if cdp_url.startswith(("ws://", "wss://")):
        return cdp_url
    base = _ip_url(cdp_url)
    info = version(base, timeout=5)
    if not info or "webSocketDebuggerUrl" not in info:
        raise ConnectionError(f"No Chrome DevTools endpoint answering at {cdp_url}")
    ws = urlparse(info["webSocketDebuggerUrl"])
    b = urlparse(base)
    return urlunparse(ws._replace(netloc=b.netloc))


def list_pages(http_url: str) -> list[dict]:
    try:
        return [t for t in _get_json(_ip_url(http_url).rstrip("/") + "/json/list") if t.get("type") == "page"]
    except Exception:
        return []
