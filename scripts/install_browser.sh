#!/usr/bin/env bash
# Install Playwright's standalone Chromium binary for Mode 2 (fresh browser instance).
set -euo pipefail
uvx playwright install chromium
