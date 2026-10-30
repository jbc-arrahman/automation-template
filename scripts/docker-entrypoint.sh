#!/usr/bin/env bash
# Container entrypoint. With ENABLE_VNC=true it starts a virtual display + noVNC so the browser can
# run headed and you can watch it at http://localhost:6080/vnc.html. Then it runs the command.
set -euo pipefail

if [[ "${ENABLE_VNC:-false}" == "true" ]]; then
  export DISPLAY="${DISPLAY:-:99}"
  Xvfb "$DISPLAY" -screen 0 "${WINDOW_WIDTH:-1366}x${WINDOW_HEIGHT:-900}x24" -nolisten tcp >/tmp/xvfb.log 2>&1 &
  sleep 1
  fluxbox >/tmp/fluxbox.log 2>&1 &
  x11vnc -display "$DISPLAY" -forever -shared -nopw -quiet -rfbport 5900 >/tmp/x11vnc.log 2>&1 &
  websockify --web /usr/share/novnc 6080 localhost:5900 >/tmp/novnc.log 2>&1 &
  export HEADLESS="${HEADLESS_WITH_VNC:-false}"
  echo "[entrypoint] noVNC live view: http://localhost:6080/vnc.html (HEADLESS=$HEADLESS)"
fi

exec "$@"
