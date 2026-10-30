# Troubleshooting Guide

Common issues across macOS, Linux, Windows, and Docker, and how to resolve them.

---

## 1. `Profile ... is already open in a Chrome WITHOUT DevTools port` / `SingletonLock`

**Symptom:** Mode 1 (`installed`) refuses to launch Chrome because `SingletonLock` (macOS/Linux) or `lockfile` (Windows) exists in `CHROME_USER_DATA_DIR`, but nothing is answering on `CDP_PORT`.

**Cause:** A Chrome process is already using that `--user-data-dir`, but it was opened without `--remote-debugging-port=9222`. When a second `chrome` command is run on the same profile directory, Chrome simply opens a new tab in the existing process and ignores `--remote-debugging-port`.

**Fix:**
1. Close the Chrome window using that profile (or run `make chrome-stop`).
2. If Chrome crashed earlier and left a stale lock file behind, delete the lock file:
   ```bash
   rm -f ./profiles/installed/Singleton* ./profiles/installed/lockfile
   ```
3. Run `make chrome` again.

---

## 2. Chrome 136+ Ignores `--remote-debugging-port` on Default Profile

**Symptom:** You pointed `CHROME_USER_DATA_DIR` at your OS default Chrome folder (`~/Library/Application Support/Google/Chrome`, `~/.config/google-chrome`, or `%LOCALAPPDATA%\Google\Chrome\User Data`) and Chrome opens, but port `9222` never starts listening.

**Cause:** Chrome 136+ disables remote debugging on the default user data directory for security.

**Fix:** Leave `CHROME_USER_DATA_DIR=./profiles/installed` (the default) and either sign in once after running `make chrome` or copy your existing profile with:
```bash
# Close your regular Chrome first, then:
make copy-profile PROFILE="Default"
```

---

## 3. `No API key for 'google'` (or another provider)

**Symptom:** `LLMConfigError: No API key for 'google'. Set LLM_API_KEY or GEMINI_API_KEY / GOOGLE_API_KEY in .env`

**Fix:**
1. Make sure `.env` exists in the project root (`cp -n .env.example .env`).
2. Set `GEMINI_API_KEY=your_key_here` (or `LLM_API_KEY=your_key_here`).
3. Verify with `make doctor`.

---

## 4. Mode 2 Fails with `No local Chrome/Chromium install found`

**Symptom:** Running in `fresh` mode on a machine without Google Chrome installed fails to find a browser binary.

**Fix:** Install Playwright's standalone Chromium binary:
```bash
make install-browser
# or on Linux if system libraries are also missing:
uvx playwright install --with-deps chromium
```

---

## 5. Corporate Proxy (`HTTP_PROXY` / `HTTPS_PROXY`) Breaks Local CDP Connection

**Symptom:** Python tries to connect to `http://127.0.0.1:9222/json/version` through an external corporate proxy and gets a `502`/`403` error.

**How this repo handles it:**
- [`app/config.py`](../app/config.py) automatically appends `127.0.0.1,localhost` to `NO_PROXY` / `no_proxy`.
- [`app/browser/cdp.py`](../app/browser/cdp.py) uses `ProxyHandler({})` so local DevTools checks never use environment proxies.
- If you connect to a custom Docker hostname in `CDP_URL`, add that hostname to `NO_PROXY` in `.env`.

---

## 6. Chromium Crashes Inside Docker (`TargetClosedError` / `Page crashed`)

**Symptom:** Browser tab crashes mid-run when running inside a container.

**Cause:** Docker defaults `/dev/shm` to `64MB`, which is too small for modern Chromium.

**Fix:** Use `docker compose` (`make docker-run`), which sets `shm_size: "2gb"` in [`docker-compose.yml`](../docker-compose.yml), or pass `--shm-size=2g` if running `docker run` directly.

---

## 7. Inspecting Why a Task Failed

Every run produces three diagnostic artifacts under `./logs/`:
1. **End-of-run screenshot:** `logs/screenshots/<timestamp>_<task>_fail.png` — shows the exact state of the page when the agent stopped.
2. **Step-by-step JSONL trace:** `logs/traces/trace_<YYYY-MM-DD>.jsonl` — shows the URL, goal, actions taken, and errors on every step:
   ```bash
   tail -n 1 logs/traces/trace_*.jsonl | python3 -m json.tool
   ```
3. **Cost & token log:** `logs/api_cost/api_cost_<YYYY-MM-DD>.log`.
