# Unity Skills REST (Besty0728/Unity-Skills)

A local REST API (default `http://localhost:8090`) with 700+ Editor operations. Use when the CLI is unavailable, for batch or multi-module operations, or to reach one of several Editors by port. Not the same thing as
Unity Technologies' own skills bundles.

## Install

1. Prerequisites: Unity 2022.3+ (Unity 6 works), localhost only. Python 3.7+ with `requests` is optional for the helper script.
2. `Packages/manifest.json` of the Unity project, under `dependencies`:
   `"com.besty.unity-skills": "https://github.com/Besty0728/Unity-Skills.git?path=/SkillsForUnity"` (append `#vX.Y.Z` to pin a version). Let the Package Manager resolve it.
3. In the Editor: `Window > UnitySkills` (Alt+Shift+U), switch the server on. The console prints `REST Server started at http://localhost:8090/`. It restarts across domain reloads when enabled.
4. Optional agent skill files: `Window > UnitySkills > AI Config > <your agent> > Install` (project or global scope), or copy the package's `unity-skills~/` folder into your agent's skills folder.

Verify: `curl -s localhost:8090/health` -> `"status":"ok"`, `projectName`, `currentMode`. A domain reload makes it unreachable for 2-5 s: retry.

## Several Editors: pick by project path

Each Editor takes the next free port in 8090-8099 and registers in `~/.unity_skills/registry.json`. Names are identical across copies of a project, so match the **path**:
`bash scripts/find-editor.sh <project folder>` prints the port, or lists what answered. Call `POST localhost:<port>/skill/project_get_info` with `{}` to read `projectPath` yourself.

## Using it

1. `GET /health` first and read `currentMode` before changing anything.
2. dryRun gate: `POST /skill/<name>?mode=dryRun` before the first run of a skill whose parameters you do not know exactly.
3. Batch multi-step work with `POST /skills/batch` or `workflow_plan`. `GET /skills/recommend?intent=...` finds the skill for a task without loading the whole schema.
4. After C# edits still run the compile-verify loop (SKILL.md).

Permission modes are set in Unity only (`Window > UnitySkills > Settings > Server`): **Auto** (most skills run, high-risk blocked), **Bypass** (unrestricted except confirmation tokens), **Approval** (each full-auto skill
needs a grant). Audit log: `<project>/Library/UnitySkillsAudit.jsonl`.

## Troubleshooting

| Problem | Fix |
|---|---|
| connection refused | Editor not open or the server toggle is off; or a domain reload is running (wait 2-5 s) |
| wrong Editor answers | match `projectPath` across ports 8090-8099 (`find-editor.sh`) |
| `MODE_RESTRICTED` | Approval mode: follow the grant protocol in the installed skill |
| package did not resolve | the first git import needs network; read the Unity console |

Uninstall: remove the package from `manifest.json`, delete the agent skill folder, or use the AI Config tab's Uninstall button.
