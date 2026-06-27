@echo off
powershell -WindowStyle Hidden -Command "Set-Location '%~dp0'; uv run python claude_launcher.py"