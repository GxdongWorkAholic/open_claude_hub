#!/usr/bin/env bash
# ============================================================
#  Open Claude Hub - Unix Shell Launcher (macOS / Linux)
#  Default: uv run python (recommended for reproducible envs)
#  Usage:   ./claude_launcher.sh
#
#  To use plain Python instead of uv:
#    Replace:  uv run python claude_launcher.py
#    With:     python3 claude_launcher.py
# ============================================================
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
uv run python claude_launcher.py
