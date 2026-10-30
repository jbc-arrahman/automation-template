# syntax=docker/dockerfile:1.7
# browser-use boilerplate - runs Mode 2 (fresh Chromium INSIDE the container) out of the box, and
# Mode 1 by attaching to a Chrome on the Docker HOST over CDP (see docs/DOCKER.md).
#
# Optional live view: ENABLE_VNC=true starts Xvfb + x11vnc + noVNC, then open
# http://localhost:6080/vnc.html to watch (or log in by hand) in the headed browser.
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    DISPLAY=:99

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /uvx /bin/

# Live-view tooling (small) + fonts so pages in any language render (e.g. CJK / emoji).
RUN apt-get update && apt-get install -y --no-install-recommends \
        xvfb x11vnc novnc websockify fluxbox \
        fonts-liberation fonts-noto-color-emoji fonts-noto-cjk \
        ca-certificates curl tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1) dependencies only (cached layer)
COPY pyproject.toml uv.lock* README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --no-install-project $( [ -f uv.lock ] && echo --frozen )

# 2) Chromium + its system libraries, managed by Playwright (browser-use finds it automatically)
RUN uvx playwright install --with-deps chromium && rm -rf /var/lib/apt/lists/*

# 3) project code
COPY app ./app
COPY scripts/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev $( [ -f uv.lock ] && echo --frozen ) \
    && chmod +x /usr/local/bin/docker-entrypoint.sh \
    && useradd -m -u 1000 bot && mkdir -p /app/logs /app/profiles && chown -R bot:bot /app

USER bot
ENV BROWSER_MODE=fresh HEADLESS=true
EXPOSE 6080
ENTRYPOINT ["/usr/bin/tini", "--", "docker-entrypoint.sh"]
CMD ["bub", "tasks"]
