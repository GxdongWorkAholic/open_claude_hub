' ============================================================
'  Open Claude Hub - Windows Silent Launcher (recommended)
'  Default: uv run python (no console window)
'  Usage:   Double-click this file to launch the GUI silently
'
'  To use plain Python instead of uv:
'    Replace:  WshShell.Run "uv run python claude_launcher.py", 0, False
'    With:     WshShell.Run "pythonw claude_launcher.py", 0, False
' ============================================================
Set WshShell = CreateObject("WScript.Shell")
scriptDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = scriptDir
WshShell.Run "uv run python claude_launcher.py", 0, False
