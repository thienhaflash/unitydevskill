# Unity CLI (Pipeline)

Docs: https://docs.unity.com/en-us/unity-production-pipeline/local-tools-cli/unity-pipeline-package

## Layers

| Layer | What | Commands |
|---|---|---|
| CLI binary | manage Unity itself (no Editor needed) | `unity install`, `unity editors`, `unity open`, `unity auth login`, `unity doctor` |
| Pipeline | drive a running Editor or dev Player over localhost | `unity command`, `unity pipeline list` / `install` |
| Built-in operations | scene, GameObjects, components, assets, tests, builds, settings | `editor_status`, `get_scene_hierarchy`, `set_component_properties`, `run_tests`, `build`, `menu` |
| `eval` | live C# REPL: no recompile, no domain reload | `unity command eval "return EditorApplication.isPlaying;"` |
| Custom | project agent tools | `[CliCommand("name")]` + `[CliArg("arg")]` on a static method in an Editor script, found after compile |
| Player | dev builds only | `unity command --runtime <name>` or `--runtime-path <port-file>` |

Agent pattern: observe, act, verify. Use `eval` for fast inspection; edit files and `compile-wait` only to persist changes.

## Prerequisites

Unity 6 Editor with the project open; `com.unity.pipeline` installed (`unity pipeline install` from the project folder); `unity` on PATH.

## Invocation

Use the wrapper `scripts/unity-cli.sh <action>`, or raw `unity command --project-path <abs path> --format json <command> ...`. Never `unity command /path/to/project` (the path is read as a command name).
The wrapper resolves the project: `UNITY_PROJECT_PATH`, then a `.unity-project` file in cwd or a parent (relative paths resolve from that file), then cwd if it has `Assets/` and `ProjectSettings/`, then the first such child folder.
Output is JSON; read `data.result`. `success: false` at the top level means the connection or invocation failed. Object handles for `--target`: `{"hierarchyPath":"/MainCamera"}`, `{"instanceId":123}`, `{"guid":"...","fileId":1}`.

## Cheat sheet

| Task | Command |
|---|---|
| Editor ready? | `unity-cli.sh status` |
| Which Editors / pipeline connected? | `unity-cli.sh pipeline` |
| Hierarchy / find | `unity-cli.sh hierarchy 50` / `unity-cli.sh find --name Foo` |
| Component properties | `unity-cli.sh cmd get_component_properties --target '{"hierarchyPath":"/Foo"}' --type Transform` |
| Set properties | `unity-cli.sh cmd set_component_properties --target '...' --type Foo --properties '{"field":1}'` |
| Add component / instantiate prefab | `cmd add_component --target '...' --type BoxCollider` / `cmd instantiate_prefab --prefab Assets/.../Foo.prefab` |
| Open scene | `cmd open_scene --path Assets/.../Scene.unity` (only when the task needs it; use the active scene otherwise) |
| Menu item | `unity-cli.sh menu "Tools/Some Item"` |
| Play / stop | `unity-cli.sh play` / `unity-cli.sh stop` |
| Read / write text asset | `unity-cli.sh read Assets/Scripts/Foo.cs` / `cmd write_text_file --path ... --contents "..."` |
| C# without recompile | `unity-cli.sh cmd eval --code "return GameObject.Find(\"Foo\")?.name;"` and `cmd eval_file --path script.cs` |
| Tests | `cmd list_tests`, `cmd run_tests --mode EditMode`, then poll `test_status` |
| Everything available | `unity-cli.sh cmd` (no arguments) |
| Compile / console | `unity-cli.sh compile-wait` / `unity-cli.sh console error 20` |

## Scene, prefab and GameObject rules

Same as `unity-mcp.md` (modify prefab assets, read before changing, preserve transforms, wire every serialized reference, save). Checklist after an edit: hierarchy read before and after, no duplicate components,
transforms preserved, required references wired (`get_component_properties`), scene or prefab saved, `compile-wait` and a clean console.

## Troubleshooting

| Problem | Fix |
|---|---|
| `unity: command not found` | source `~/.unity/env` or open a new terminal |
| `No Unity Editor instances found` | open the project in the Editor |
| `Pipeline: false` | `unity pipeline install` from the project folder, let it compile |
| fails during compile | domain reload takes 5-15 s: retry `status` |
| `401` or another project answers | wrong Editor: see SKILL.md Rule 1, use `find-editor.sh` and the Skills REST port |
| `Command Not Found: /path/...` | use `--project-path`, not a positional path |
