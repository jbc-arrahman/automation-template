"""Mode 1 - automate the Google Chrome that is INSTALLED on this device.

Two ways to get a Chrome to drive (INSTALLED_ACTION):

  launch  We start the installed Chrome ourselves on CHROME_USER_DATA_DIR with a DevTools port,
          detached from this process, so it keeps running after the task (logins, open tabs and
          cookies stay). The next run finds it on the port and re-uses it. This is the recommended
          mode for authenticated workflows.
  attach  Chrome is already running with --remote-debugging-port (you started it with
          `make chrome`, scripts/launch_chrome.*, or it lives on another machine / the Docker
          host). We only connect to it.

Chrome 136+ ignores --remote-debugging-port on your DEFAULT profile directory (security change).
Use a dedicated directory (default: ./profiles/installed) and log in there once, or copy your
real profile into it with `copy_profile()` / `make copy-profile`. See README.md.
"""
from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from app.browser import cdp
from app.config import Settings

log = logging.getLogger(__name__)

SYSTEM = platform.system()  # Darwin | Linux | Windows

_CHROME_CANDIDATES = {
    "Darwin": [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    ],
    "Linux": [
        "/usr/bin/google-chrome-stable", "/usr/bin/google-chrome", "/opt/google/chrome/chrome",
        "/usr/bin/chromium", "/usr/bin/chromium-browser", "/snap/bin/chromium",
        "/usr/bin/brave-browser", "/usr/bin/microsoft-edge-stable",
    ],
    "Windows": [
        r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe",
        r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe",
        r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
        r"%PROGRAMFILES(X86)%\Microsoft\Edge\Application\msedge.exe",
        r"%PROGRAMFILES%\Microsoft\Edge\Application\msedge.exe",
    ],
}

# The user's everyday Chrome data dirs. Chrome 136+ will not expose CDP on these.
_DEFAULT_USER_DATA_DIRS = {
    "Darwin": ["~/Library/Application Support/Google/Chrome"],
    "Linux": ["~/.config/google-chrome", "~/.config/chromium"],
    "Windows": [r"%LOCALAPPDATA%\Google\Chrome\User Data"],
}

_PID_FILE = ".automation_chrome.pid"


def _expand(p: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(p)))


def default_user_data_dirs() -> list[Path]:
    return [_expand(p) for p in _DEFAULT_USER_DATA_DIRS.get(SYSTEM, [])]


def find_chrome_binary(override: str = "") -> str:
    """Path of the installed Chrome (or Chromium/Brave/Edge as fallback)."""
    if override:
        p = _expand(override)
        if p.exists():
            return str(p)
        raise FileNotFoundError(f"CHROME_BINARY={override} does not exist")
    for c in _CHROME_CANDIDATES.get(SYSTEM, []):
        p = _expand(c)
        if p.exists():
            return str(p)
    for name in ("google-chrome-stable", "google-chrome", "chromium", "chromium-browser", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    raise FileNotFoundError("Google Chrome not found. Install it, or set CHROME_BINARY in .env")


def _is_default_profile_dir(user_data_dir: Path) -> bool:
    try:
        target = user_data_dir.resolve()
        return any(target == d.resolve() for d in default_user_data_dirs())
    except OSError:
        return False


def _profile_locked(user_data_dir: Path) -> bool:
    """Another Chrome already holds this profile (Chrome would just open a window in THAT process
    and our DevTools port would never appear)."""
    if SYSTEM == "Windows":
        lock = user_data_dir / "lockfile"
        if not lock.exists():
            return False
        try:  # Windows keeps the lockfile open while Chrome runs; deleting it fails if in use.
            lock.unlink()
            return False
        except OSError:
            return True
    return os.path.islink(user_data_dir / "SingletonLock")


def build_launch_command(settings: Settings, binary: Optional[str] = None) -> list[str]:
    s = settings
    cmd = [
        binary or find_chrome_binary(s.chrome_binary),
        f"--remote-debugging-port={s.cdp_port}",
        "--remote-debugging-address=127.0.0.1",
        f"--user-data-dir={s.chrome_user_data_dir}",
        f"--profile-directory={s.chrome_profile_directory}",
        f"--window-size={s.window_width},{s.window_height}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-features=Translate,MediaRouter",
        *s.extra_chrome_args,
    ]
    if s.headless:
        cmd.append("--headless=new")
    return cmd


def launch_chrome(settings: Settings) -> int:
    """Start the installed Chrome detached (it outlives this process). Returns its PID."""
    udd = settings.chrome_user_data_dir
    if _is_default_profile_dir(udd):
        raise RuntimeError(
            f"CHROME_USER_DATA_DIR points at your everyday Chrome profile ({udd}). Chrome 136+ blocks "
            "remote debugging there. Use a dedicated dir (default ./profiles/installed) or copy your "
            "profile first: `make copy-profile` (see README.md)."
        )
    udd.mkdir(parents=True, exist_ok=True)
    if _profile_locked(udd):
        raise RuntimeError(
            f"Profile {udd} is already open in a Chrome WITHOUT DevTools port {settings.cdp_port}. "
            "Close that Chrome window (or run `make chrome-stop`) and try again."
        )

    cmd = build_launch_command(settings)
    log.info("Launching installed Chrome on CDP :%s with profile %s", settings.cdp_port, udd)
    kwargs: dict = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "stdin": subprocess.DEVNULL}
    if SYSTEM == "Windows":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
    else:
        kwargs["start_new_session"] = True
        if SYSTEM == "Linux":
            kwargs["env"] = {**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":0")}
    proc = subprocess.Popen(cmd, **kwargs)
    (udd / _PID_FILE).write_text(str(proc.pid))
    return proc.pid


def ensure_chrome(settings: Settings, wait_sec: float = 20.0) -> str:
    """Return a CDP URL for a running Chrome, launching one first if INSTALLED_ACTION=launch."""
    url = settings.resolved_cdp_url
    if cdp.is_ready(url):
        log.info("Re-using Chrome already listening on %s", url)
        return url
    if settings.installed_action == "attach":
        raise ConnectionError(
            f"INSTALLED_ACTION=attach but no Chrome answers at {url}. Start one with `make chrome` "
            f"(or scripts/launch_chrome.*) first."
        )
    if settings.cdp_host not in ("127.0.0.1", "localhost") or settings.cdp_url:
        raise ConnectionError(f"Cannot launch Chrome on a remote host ({url}); use INSTALLED_ACTION=attach.")
    launch_chrome(settings)
    deadline = time.time() + wait_sec
    while time.time() < deadline:
        if cdp.is_ready(url):
            return url
        time.sleep(0.5)
    raise TimeoutError(f"Chrome did not open DevTools port {settings.cdp_port} within {wait_sec:.0f}s")


def close_chrome(settings: Settings) -> bool:
    """Stop the Chrome we launched on this profile (uses the PID file written by launch_chrome)."""
    pid_file = settings.chrome_user_data_dir / _PID_FILE
    if not pid_file.exists():
        return False
    try:
        import psutil  # installed with browser-use

        proc = psutil.Process(int(pid_file.read_text().strip()))
        for child in proc.children(recursive=True):
            child.terminate()
        proc.terminate()
        psutil.wait_procs([proc], timeout=10)
    except Exception as e:  # already gone, permission, ...
        log.debug("close_chrome: %s", e)
    pid_file.unlink(missing_ok=True)
    return True


_COPY_IGNORE = shutil.ignore_patterns(
    "Singleton*", "lockfile", "*.tmp", "Cache", "Code Cache", "GPUCache", "DawnCache",
    "GrShaderCache", "ShaderCache", "Service Worker", "Safe Browsing*", "Crashpad",
)


def copy_profile(source_user_data_dir: Path, profile_directory: str, target_user_data_dir: Path) -> Path:
    """Copy one profile (e.g. "Default" or "Profile 1") + "Local State" from your everyday Chrome
    into a dedicated dir that Chrome allows remote debugging on. Close Chrome first.

    Cookies are encrypted with an OS key; on the same machine and user they usually keep working
    (macOS Keychain / Linux keyring / Windows DPAPI). Some sites (Google included) may still ask
    you to sign in again once - do that in `make chrome`, the session then sticks to this copy.
    """
    src_profile = source_user_data_dir / profile_directory
    if not src_profile.is_dir():
        raise FileNotFoundError(f"No profile '{profile_directory}' in {source_user_data_dir}")
    target_user_data_dir.mkdir(parents=True, exist_ok=True)
    dst_profile = target_user_data_dir / profile_directory
    if dst_profile.exists():
        shutil.rmtree(dst_profile)
    shutil.copytree(src_profile, dst_profile, ignore=_COPY_IGNORE)
    local_state = source_user_data_dir / "Local State"
    if local_state.exists():
        shutil.copy2(local_state, target_user_data_dir / "Local State")
    log.info("Copied profile %s -> %s", src_profile, dst_profile)
    return dst_profile


if __name__ == "__main__":  # pragma: no cover - `python -m app.browser.installed` prints the binary
    print(find_chrome_binary(sys.argv[1] if len(sys.argv) > 1 else ""))
