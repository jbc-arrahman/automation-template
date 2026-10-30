# Browser Modes: `installed` (Mode 1) vs `fresh` (Mode 2)

This boilerplate supports two distinct ways to drive a browser, selectable via `BROWSER_MODE` in `.env` or `--mode installed|fresh` on the CLI (`MODE=installed|fresh` in `make`).

---

## Side-by-Side Comparison

| Aspect | Mode 1: `installed` *(Recommended)* | Mode 2: `fresh` |
|---|---|---|
| **Browser binary** | Your device's installed Google Chrome (or Brave/Edge/Chromium fallback) | Playwright's standalone Chromium (`make install-browser`) or auto-detected local browser |
| **How it connects** | Attaches over Chrome DevTools Protocol (`--remote-debugging-port`) | Spawned and owned directly by `browser-use` |
| **Lifecycle after task** | **Stays open** (`keep_alive=True`) so the next task reuses the same window & tabs | **Closed & cleaned up** automatically when the task finishes |
| **Cookies & logins** | Persistent in `CHROME_USER_DATA_DIR` (`./profiles/installed` by default) | Either **ephemeral** (deleted after run) or **persistent** (`./profiles/fresh/<name>`) |
| **Best for** | Google accounts, 2FA/SSO portals, anti-bot sensitive sites, multi-task workdays | Stateless scraping, clean-room testing, parallel workers, CI/CD & headless Docker |

---

## Mode 1: Automation with the Installed Browser (`BROWSER_MODE=installed`)

In Mode 1 ([`app/browser/installed.py`](../app/browser/installed.py)), the agent connects to the real Google Chrome installed on your macOS, Linux, or Windows device via its DevTools port (`CDP_PORT`, default `9222`).

### Two Sub-modes (`INSTALLED_ACTION`)

1. **`INSTALLED_ACTION=launch` (Default)**
   - If Chrome is already listening on `CDP_PORT`, the runner attaches to it immediately.
   - If not, the runner launches your installed Chrome in a detached process using `CHROME_USER_DATA_DIR`, waits for `CDP_PORT` to come up, and attaches.
   - When the task finishes, Chrome **remains open** (`CLOSE_INSTALLED_ON_EXIT=false`), ready for the next run.

2. **`INSTALLED_ACTION=attach`**
   - The runner never spawns Chrome itself; it requires a Chrome instance to already be listening at `CDP_HOST:CDP_PORT` (or `CDP_URL`).
   - Use this when you start Chrome manually (`make chrome` / `./scripts/launch_chrome.sh` / `.\scripts\launch_chrome.ps1`) or when running inside Docker while attaching to Chrome on the host (`make docker-run-installed`).

### ⚠️ Important: Chrome 136+ and the Default Profile Directory

Starting in **Chrome 136**, Google Chrome **ignores `--remote-debugging-port` if `--user-data-dir` points to the OS default Chrome profile directory** (e.g., `~/Library/Application Support/Google/Chrome` on macOS, `~/.config/google-chrome` on Linux, `%LOCALAPPDATA%\Google\Chrome\User Data` on Windows).

To work with Chrome 136+, Mode 1 uses a dedicated `--user-data-dir` (`./profiles/installed` by default). You have two ways to populate it with your logins:

#### Option 1: Log in once inside the automation profile (Recommended)
```bash
# Opens installed Chrome on ./profiles/installed with port 9222 active
make chrome
```
Sign in to Google or your target websites in that window. Because `./profiles/installed` is persistent on disk, your cookies and logins stay signed in across restarts.

#### Option 2: Copy an existing Chrome profile into `./profiles/installed`
If you already have an aged profile in your everyday Chrome (`Default`, `Profile 1`, etc.):
1. **Quit your everyday Google Chrome completely** (so profile locks are released).
2. Run:
   ```bash
   make copy-profile PROFILE="Default"
   # or for a named profile:
   make copy-profile PROFILE="Profile 1"
   ```
3. Launch and verify:
   ```bash
   make chrome
   make chrome-status
   ```

### Useful Mode 1 Commands

```bash
make chrome                # Start installed Chrome with CDP port open
make chrome-status         # Check if Chrome is answering on CDP_PORT (shows version & open tab count)
make chrome-stop           # Stop the Chrome process started by `make chrome`
make run-installed TASK=hn_top_stories INPUT="count=5"
```

---

## Mode 2: Automation with a Completely New Instance (`BROWSER_MODE=fresh`)

In Mode 2 ([`app/browser/fresh.py`](../app/browser/fresh.py)), `browser-use` launches a brand-new Chromium process for the task and terminates it when `run_task()` finishes.

### Profile Options (`FRESH_PROFILE`)

1. **`FRESH_PROFILE=ephemeral` (Default)**
   - Creates a fresh temporary directory (`browser-use-user-data-dir-*`) before the run and deletes it on exit.
   - Zero state leaks between runs — every execution starts with empty cookies, empty storage, and a clean cache.

2. **`FRESH_PROFILE=persistent`**
   - Stores the profile at `./profiles/fresh/<FRESH_PROFILE_NAME>` (default `./profiles/fresh/default`).
   - Useful when you want `browser-use` to manage the browser lifecycle (start on run, kill on exit), while still keeping cookies/localStorage between runs.
   - You can maintain multiple isolated identities by switching `FRESH_PROFILE_NAME=account_a`, `FRESH_PROFILE_NAME=account_b`.

### Headed vs Headless

- Set `HEADLESS=true` in `.env` (or pass `--headless` / `HEADLESS=1`) for background or server execution.
- Set `HEADLESS=false` (or pass `--headed`) to watch the browser window on your desktop.

### Installing the Standalone Browser Binary for Mode 2

If your machine already has Google Chrome installed, Mode 2 can use it automatically. For a completely self-contained Playwright Chromium binary (or on a fresh Linux server):

```bash
make install-browser
# equivalent to: uvx playwright install chromium
```
