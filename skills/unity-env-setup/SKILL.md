---
name: unity-env-setup
description: >-
  Set up and operate the tooling that lets an agent drive the Unity Editor and read Unity C#: Unity CLI + com.unity.pipeline (eval, compile-wait, console), the Unity Skills REST
  server (Besty0728/Unity-Skills), Unity MCP, the compile-verify loop, how to find the Editor of the right project when several are open, and C# code hints
  (OmniSharp in VS Code / Cursor). Use for "set up Unity for agents", "unity cli", "pipeline", "unity skills", "unity mcp", "401 / wrong project / port", "C# intellisense / go to definition",
  "compile and check the console", "new machine setup", "git lfs / pointer files", "Safe Mode", "Unity will not open".
---

# Unity environment setup for agents

Machine- and project-agnostic. Order of preference for driving an Editor: **Unity CLI (Pipeline) -> Unity Skills REST -> Unity MCP**. Use the next layer only when the previous one is not installed or lacks the command.

| Layer | Strength | Reference |
|---|---|---|
| Unity CLI + `com.unity.pipeline` | official, light, `eval` = live C# with no recompile and no domain reload, compile/console/tests/builds | `reference/unity-cli.md` |
| Unity Skills REST (`com.besty.unity-skills`) | 700+ Editor operations over localhost HTTP, batch, dry-run, several Editors by port | `reference/unity-skills-rest.md` |
| Unity MCP | fallback when neither of the above can do it; prefab and scene rules | `reference/unity-mcp.md` |
| Editor lifecycle: Git LFS, open per worktree, cap of 5, 2-min hang rule, reconnect, Safe Mode dialog | `reference/editor-lifecycle.md` |
| C# code hints | go-to-definition and IntelliSense in the code editor | `reference/csharp-code-hints.md` |

## Rule 0: Git LFS first, Safe Mode second (the two things that most often leave an agent stuck)

1. In a fresh clone or worktree, or after switching branches, run `git lfs pull` **before** opening the Editor. Binaries (DOTween.dll, textures, audio) are LFS pointers until then: the first import fails with hundreds of compile errors and the Editor sits in Safe Mode. `ensure-editor.sh` does this for you. A tracked binary that is a ~130-byte text file starting with `version https://git-lfs` is still a pointer.
2. If the Editor shows "Enter Safe Mode?" or stays in Safe Mode, click **Ignore** (or **Exit Safe Mode**) with computer use; do not ask the user to do it and do not kill the Editor (`reference/editor-lifecycle.md`).
3. Switch on **Start On Editor Launch** in Unity Skills for the project, so the REST port comes up on every launch (`reference/unity-skills-rest.md`, "Auto enable").
4. Only after 1-3: Rule 1 below.

### Rule 0b: avoid the Safe Mode popup altogether (empty-project launch)

Safe Mode is only offered at **launch**, when the project has compile errors. A fresh worktree usually has them (packages not resolved, SDK profile not applied, private UPM git deps unreachable). So launch with an empty project, let Unity resolve packages, then put the real project back while the Editor is already open. Unity then just recompiles; no dialog. Needs the user's OK to kill an Editor if one is already open on that worktree; otherwise nothing is killed.

1. Prepare what the packages need first (repo-specific; read its CLAUDE.md/docs): e.g. a git-ignored live `Packages/manifest.json` generated from a profile script, and for private `https://gitlab...` UPM deps the one-time `git config --global url."git@host:".insteadOf "https://host/"` (check `ssh -T git@host` works). Without these the resolve fails even in the empty project.
2. Close this worktree's Editor if open (by pid, never another project's). Then, from the Unity project folder:
   ```bash
   mv Assets Assets_REAL && mv ProjectSettings ProjectSettings_REAL
   mkdir Assets ProjectSettings && cp ProjectSettings_REAL/ProjectVersion.txt ProjectSettings/
   ```
   Unity refuses a folder with no `Assets`/`ProjectSettings` ("Couldn't set project path", it exits), and without `ProjectVersion.txt` it may upgrade; so create the two empty folders and copy only the version file.
3. Open it (`open -g -n -a <Unity.app> --args -projectPath <project>`) and wait until packages are resolved (log has `Done resolving packages`, `Library/PackageCache` holds the git/registry packages, no `An error occurred while resolving`). Package changes made while the Editor sits unfocused in the background are not picked up; relaunch the empty project instead of waiting.
4. With the Editor up: `rm -rf Assets ProjectSettings` (the generated empty ones), then `mv Assets_REAL Assets && mv ProjectSettings_REAL ProjectSettings`. Unity refreshes and recompiles by itself (focus the Editor or call the Skills/CLI refresh if it does not notice). Check `git status` shows no stray changes in `Assets`/`ProjectSettings`, then compile-wait and read the console.
   Verified on a fresh worktree: after the swap-back the Editor recompiled with no Safe Mode dialog (`Library/Bee` and `ScriptAssemblies` appear). An Editor sitting in the background may take a moment to notice; it was never focused.
   Gotchas: (a) wipe `Library`/`Temp` first if an earlier open left a half-built `Library` (a `LibraryInitializing` marker, or an empty-project Editor idle at 0% CPU / <100 MB); (b) `~/Library/Logs/Unity/Editor.log` is shared by all Editors and gets taken over ("Logs moved to project-relative Editor.log") by whichever opened last, so check resolve progress through `Library/PackageCache` instead; (c) Unity Skills needs Unity 2022.3+ and Pipeline needs a newer Editor, so on an older project (e.g. 2021.3) no port will ever answer: tell the user instead of waiting.
5. If the project's `ProjectVersion.txt` names an Editor version that is not installed, install it first (`Unity Hub -- --headless install --version V --changeset C --architecture arm64 --module android ...`, with prompts answered, e.g. `yes "" |`; start it in the background and read its log, a prompt hangs it silently).

## Rule 1: always talk to the Editor of the project you work in

Several Editors are usually open (main checkout, worktrees, other projects). The default CLI port belongs to whichever Editor started first, not to yours.

1. List them and their project paths: `unity pipeline list` (run inside a project folder), or `bash scripts/unity-cli.sh pipeline`.
2. Target explicitly: `UNITY_PROJECT_PATH=<absolute project folder>` or `unity command --project-path <absolute folder> ...`. In a git worktree the project path is the worktree's copy, never the main checkout.
3. If the CLI answers `401`, shows another project, or cannot reach yours, change route instead of giving up: `bash scripts/find-editor.sh [project folder]` probes Unity Skills ports 8090-8099 and prints the port whose
   `projectPath` equals your project (match the **path**; every copy has the same project name). Then call `localhost:<port>/skill/<name>`.
   If the table and the probe still do not make clear which port is yours, **ask the user for the correct port**, listing each port and `projectPath` you probed. Do not guess and do not stop at "port held by another Editor".
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
