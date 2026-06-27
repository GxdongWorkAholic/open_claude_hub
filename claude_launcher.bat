@echo off
REM ============================================================
REM  Open Claude Hub - Windows Batch Launcher
REM  Default: uv run python (recommended for reproducible envs)
REM  Usage:   Double-click this file to launch the GUI
REM
REM  To use plain Python instead of uv:
REM    Replace:  uv run python claude_launcher.py
REM    With:     python claude_launcher.py
REM ============================================================
powershell -WindowStyle Hidden -Command "Set-Location '%~dp0'; uv run python claude_launcher.py"
