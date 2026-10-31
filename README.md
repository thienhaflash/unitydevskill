# unitydevskill

Project- and machine-agnostic skills for agents working on Unity games.

| Skill | What it does |
|---|---|
| `game-profile-optimize` | Profile and optimize a Unity game: Editor Profiler `.data` analysis, Android device sweeps, cost per feature, device-tier matrix, change log, generated report. Game data lives in the game's repo (`.claude/perf/<game>/`). |
| `logic-flow` | Turn code behavior into user-story flow graphs in a plain-text `.flow` format and render an interactive HTML page (`scripts/extract_flow_data.py`, `scripts/render_flow.py`). |
| `unity-env-setup` | Set up and operate Unity CLI (Pipeline), Unity Skills REST, Unity MCP, the compile-verify loop, finding the right Editor by project path, and C# code hints in VS Code / Cursor. |

Install by copying or symlinking `skills/<name>` into `~/.claude/skills/` (or a project's `.claude/skills/`).
