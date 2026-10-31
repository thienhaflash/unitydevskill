---
name: unity-env-setup
description: >-
  Set up and operate the tooling that lets an agent drive the Unity Editor and read Unity C#: Unity CLI + com.unity.pipeline (eval, compile-wait, console), the Unity Skills REST
  server (Besty0728/Unity-Skills), Unity MCP, the compile-verify loop, how to find the Editor of the right project when several are open, and C# code hints
  (OmniSharp in VS Code / Cursor). Use for "set up Unity for agents", "unity cli", "pipeline", "unity skills", "unity mcp", "401 / wrong project / port", "C# intellisense / go to definition",
  "compile and check the console", "new machine setup".
---

# Unity environment setup for agents

Machine- and project-agnostic. Order of preference for driving an Editor: **Unity CLI (Pipeline) -> Unity Skills REST -> Unity MCP**. Use the next layer only when the previous one is not installed or lacks the command.

| Layer | Strength | Reference |
|---|---|---|
| Unity CLI + `com.unity.pipeline` | official, light, `eval` = live C# with no recompile and no domain reload, compile/console/tests/builds | `reference/unity-cli.md` |
| Unity Skills REST (`com.besty.unity-skills`) | 700+ Editor operations over localhost HTTP, batch, dry-run, several Editors by port | `reference/unity-skills-rest.md` |
| Unity MCP | fallback when neither of the above can do it; prefab and scene rules | `reference/unity-mcp.md` |
| Editor lifecycle: open per worktree, cap of 5, 2-min hang rule, reconnect, Safe Mode dialog | `reference/editor-lifecycle.md` |
| C# code hints | go-to-definition and IntelliSense in the code editor | `reference/csharp-code-hints.md` |

## Rule 1: always talk to the Editor of the project you work in

Several Editors are usually open (main checkout, worktrees, other projects). The default CLI port belongs to whichever Editor started first, not to yours.

1. List them and their project paths: `unity pipeline list` (run inside a project folder), or `bash scripts/unity-cli.sh pipeline`.
2. Target explicitly: `UNITY_PROJECT_PATH=<absolute project folder>` or `unity command --project-path <absolute folder> ...`. In a git worktree the project path is the worktree's copy, never the main checkout.
3. If the CLI answers `401`, shows another project, or cannot reach yours, change route instead of giving up: `bash scripts/find-editor.sh [project folder]` probes Unity Skills ports 8090-8099 and prints the port whose
   `projectPath` equals your project (match the **path**; every copy has the same project name). Then call `localhost:<port>/skill/<name>`.
4. Verify the `projectPath` of the endpoint before every build or write. Never drive an Editor of another project.
5. Never kill, restart or focus an Editor (focus steals the user's window). Opening one for your worktree, the 5-Editor cap, the 120 s hang rule and reconnecting: `reference/editor-lifecycle.md`. If none of your routes works, report which ones you probed (CLI table, ports, each `projectPath`) before asking the user anything.

## Compile-verify loop (after every C# edit)

```
1. stop play mode        2. compile and wait (domain reload disconnects the Editor for 5-15 s; the wrapper retries)
3. console errors: zero  (else fix and go to 2)        4. only then say it is done
```
With the wrapper: `unity-cli.sh stop && unity-cli.sh compile-wait && unity-cli.sh console error 20`. A state that never changes (`compiling` stays true, a test run stays `running`) is a stuck Editor, not something to wait out:
poll 30-60 s, then `unity-cli.sh cmd recompile` and re-check; for a stuck test run cancel and start again. Do not wait for minutes on an unchanged state.

## Setup checklist (new machine or new project)

1. Unity CLI installed and signed in (`unity auth login`); `unity doctor` is clean. Put `~/.unity/env` on the shell path if the installer created it (the wrapper sources it).
2. In each project: `unity pipeline install` (adds `com.unity.pipeline`), open the project in the Editor, `unity-cli.sh status` answers `ready`.
3. Monorepo: add a `.unity-project` file at the repo root containing the relative path of the Unity folder, so the wrapper finds it from anywhere in the repo.
4. Optional: install Unity Skills (`reference/unity-skills-rest.md`) for the REST route and multi-Editor discovery.
5. Optional: Unity MCP (`reference/unity-mcp.md`) only if you need it.
6. C# hints: `bash scripts/setup-csharp-lsp.sh [code|cursor]`, then regenerate project files in Unity (`reference/csharp-code-hints.md`).
7. Verify with `unity-cli.sh status`, `unity-cli.sh compile-wait`, `unity-cli.sh console error 5`, and `scripts/find-editor.sh`.

## Files

- `scripts/unity-cli.sh`: project resolution (env var, `.unity-project`, cwd, monorepo child), `status`, `pipeline`, `console`, `compile-wait`, `play/stop/pause`, `hierarchy`, `find`, `menu`, `read`, `cmd <any pipeline command>`.
- `scripts/ensure-editor.sh`: returns the REST port of this project's Editor, launching one in the background only if none is open and fewer than 5 are running; exit 2 = cap, 3 = not answering in 120 s (never kills).
- `scripts/find-editor.sh`: the Skills-REST port of the Editor that has a given project open.
- `scripts/setup-csharp-lsp.sh`: installs the C# extension and OmniSharp for VS Code or Cursor (macOS, Linux).
- `reference/`: `unity-cli.md`, `unity-skills-rest.md`, `unity-mcp.md`, `csharp-code-hints.md`.
