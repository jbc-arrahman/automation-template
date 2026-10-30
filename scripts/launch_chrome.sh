#!/usr/bin/env bash
# Launch the device's installed Google Chrome with a CDP debugging port (macOS & Linux).
# Usage: ./scripts/launch_chrome.sh [PORT] [USER_DATA_DIR]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

PORT="${1:-${CDP_PORT:-9222}}"
USER_DATA_DIR="${2:-${CHROME_USER_DATA_DIR:-$ROOT_DIR/profiles/installed}}"
PROFILE_DIR="${CHROME_PROFILE_DIRECTORY:-Default}"

find_chrome() {
  if [[ -n "${CHROME_BINARY:-}" && -x "$CHROME_BINARY" ]]; then
    echo "$CHROME_BINARY"; return
  fi
  case "$(uname -s)" in
    Darwin)
      for c in \
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
        "$HOME/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
        "/Applications/Chromium.app/Contents/MacOS/Chromium" \
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"; do
        [[ -x "$c" ]] && { echo "$c"; return; }
      done
      ;;
    Linux)
      for c in /usr/bin/google-chrome-stable /usr/bin/google-chrome /opt/google/chrome/chrome \
               /usr/bin/chromium /usr/bin/chromium-browser /snap/bin/chromium; do
        [[ -x "$c" ]] && { echo "$c"; return; }
      done
      ;;
  esac
  echo "Error: Google Chrome binary not found. Set CHROME_BINARY in .env" >&2
  exit 1
}

BIN="$(find_chrome)"
mkdir -p "$USER_DATA_DIR"

echo "Starting Chrome:"
echo "  Binary        : $BIN"
echo "  CDP Port      : http://127.0.0.1:$PORT"
echo "  User Data Dir : $USER_DATA_DIR ($PROFILE_DIR)"

nohup "$BIN" \
  "--remote-debugging-port=$PORT" \
  "--remote-debugging-address=127.0.0.1" \
  "--user-data-dir=$USER_DATA_DIR" \
  "--profile-directory=$PROFILE_DIR" \
  "--no-first-run" \
  "--no-default-browser-check" \
  >/dev/null 2>&1 &

echo "Launched (PID $!). Verify with: curl -s http://127.0.0.1:$PORT/json/version"
