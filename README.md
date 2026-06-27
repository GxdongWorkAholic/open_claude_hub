# 🚀 Open Claude Hub

A Tkinter-based GUI launcher that manages Claude Code sessions across multiple projects, with **Headroom** proxy integration for token savings and **ccswitch** for API key management.

## 🏗️ Architecture

```
Claude CLI  →  Headroom (:8787)  →  ccswitch (:15721)  →  Anthropic API
   ▲                 ▲                    ▲
   │                 │                    │
ANTHROPIC_BASE_URL  headroom.host+port   headroom.upstream
  (auto-injected)   (from config)        (from config)
```

## ✨ Features

- 📂 **Project Management** — Launch Claude Code in multiple project directories with one click, each in its own terminal window.
- 📊 **Headroom Integration** — Auto-starts and health-checks the Headroom proxy; displays live token/cost/savings statistics every 5 seconds.
- 🔗 **ccswitch Compatible** — Upstream points to ccswitch for API key routing, no additional configuration needed.
- ⚙️ **Config-Driven** — All settings (host, port, upstream, projects) are read from `claude_config.json`, nothing hardcoded.

## 📋 Requirements

- 🐍 **Python 3** — that's it! tkinter is included in the standard library, no extra packages needed.
- 🧠 **headroom.exe** on PATH — for the proxy layer.

## 🛠️ Setup

1. Copy the config template and fill in your own values:
   ```
   cp claude_config.template.json claude_config.json
   ```

2. Edit `claude_config.json`:
   ```json
   {
       "headroom": {
           "host": "127.0.0.1",
           "port": 8787,
           "upstream": "http://127.0.0.1:15721"
       },
       "projects": [
           {
               "name": "my_project",
               "path": "D:\\path\\to\\your\\project"
           }
       ]
   }
   ```

   | Field | Description |
   |-------|-------------|
   | `headroom.host` | Headroom proxy bind address |
   | `headroom.port` | Headroom proxy listen port |
   | `headroom.upstream` | Upstream API URL (ccswitch or direct Anthropic endpoint) |
   | `projects[].name` | Display name for the project |
   | `projects[].path` | Absolute path to the project directory (must exist) |

3. Run it:
   ```
   uv run python claude_launcher.py
   ```
   Or double-click `claude_launcher.vbs` / `claude_launcher.bat`.

### 🔧 Using plain Python instead of uv

The default launchers use `uv run python`. If you prefer plain Python, edit the launcher files:

| Launcher | Default | Plain Python |
|----------|---------|---------------|
| `.bat` | `uv run python claude_launcher.py` | `python claude_launcher.py` |
| `.vbs` | `uv run python claude_launcher.py` | `pythonw claude_launcher.py` |
| `.sh` | `uv run python claude_launcher.py` | `python3 claude_launcher.py` |

## 🖥️ Usage

Just double-click the launcher:

| File | Platform | Notes |
|------|----------|-------|
| `claude_launcher.vbs` | Windows | 🏆 **Recommended** — silent launch, no console window |
| `claude_launcher.bat` | Windows | Launches via PowerShell (hidden window) |
| `claude_launcher.sh` | macOS / Linux | `chmod +x claude_launcher.sh` then `./claude_launcher.sh` |

Or from the terminal:
```
uv run python claude_launcher.py
```

### 📑 Tabs

| Tab | Purpose |
|-----|---------|
| 📂 **Projects** | Select projects and click **Launch Selected** to open Claude Code in each project's directory |
| 📊 **Headroom** | Live statistics: tokens saved, API requests, savings %, per-project breakdown, RTK commands, cost analysis |

### 🔘 Buttons

| Button | Action |
|--------|--------|
| ☑️ Select All / Deselect All | Toggle all project checkboxes |
| 🚀 Launch Selected | Start Claude Code in each selected project's directory |

### 💡 Header Indicator

| Dot | Meaning |
|-----|---------|
| 🟢 Green | Headroom proxy is running |
| ⚫ Gray | Headroom proxy is offline |

## 📁 Files

| File | Purpose | Tracked |
|------|---------|:---:|
| `claude_config.json` | Your config (real data) | ❌ |
| `claude_config.template.json` | Config template (placeholders) | ✅ |
| `claude_launcher.py` | Main application | ✅ |
| `claude_launcher.vbs` | Windows silent launcher **(recommended)** | ✅ |
| `claude_launcher.bat` | Windows batch launcher | ✅ |
| `claude_launcher.sh` | macOS / Linux shell launcher | ✅ |
| `.gitignore` | Ignores real config and bytecode | ✅ |

## 🔄 How It Works

1. 📖 On launch, reads `claude_config.json` and renders the project list.
2. 🚀 Automatically starts `headroom proxy --port <port> --anthropic-api-url <upstream>`.
3. 🔄 Polls `http://<host>:<port>/stats` every 5 seconds for live metrics.
4. 🔗 When a project is launched, sets `ANTHROPIC_BASE_URL=http://<host>:<port>` so Claude Code routes through Headroom → ccswitch.
5. 🧹 On exit, kills all spawned child processes and the Headroom proxy.
