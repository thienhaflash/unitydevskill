---
name: game-profile-optimize
description: >-
  Profile and monitor the frame rate and GPU cost of a Unity game on the Editor and on an Android phone, break the cost down per feature, and keep a report
  (fps per unit/level/section, cost per switch, changes over the builds, what each optimization did, device-tier matrix) generated from data.
  Project- and machine-agnostic: the game's profile and measurements live in the game's repo (.claude/perf/<game>/). Use for "profile", "profiler .data", "frame spikes", "GC", "fps", "60 fps",
  "Android perf", "GPU cost", "which feature costs", "optimize shaders/particles/shadows", "update the perf report", "measure on a new phone", "add a game to the profiler".
---

# Game profile and optimize (Unity): profile, break down, monitor

Output you are after: **the cost in ms of every feature**, the fps of every unit/level/section, and a report that updates itself from the measurements.
The skill knows no game and no machine. Everything specific to a game lives **in that game's repo** under `.claude/perf/<game>/`:

```
.claude/perf/<game>/profile.json   units, sections, levels, switches, menus, page text   (start from examples/profile.example.json)
                    runs.ndjson    every reading, tagged game/build/commit/device/tier/scale/level/unit/section
                    builds.json    the build history          effects.json  what each optimization did          status.md  where it stands
                    devices.json   optional tier override     shots/  history/  switches.md  techniques.md (the game's own notes)
                    out/           raw logs, git-ignored
```
Run the scripts from inside the game's checkout (`GAME=<id>` when it has several profiles; `PERF_DIR=<folder>` to point anywhere). A repo without `.claude/perf/` has no profile yet:
see `reference/harness-protocol.md`, "Adding a game". Needs `adb`, Python 3, `curl`, a phone on USB debugging.

Reading order: `reference/editor-profiler.md` (Editor `.data` capture: extract, rank, decision tree) and `reference/device-gate-and-loop.md` (the device gate, GPU vs CPU
classification, the one-hypothesis improve loop, Android preparation, anti-patterns); then `reference/techniques.md` first (how cost behaves on mobile GPUs, how to measure), the game's own `techniques.md` (what was tried), then work through the steps.
`reference/checks.md` is what to check after a result.

## Rules that apply to every step

- **Find the Editor of this checkout by path.** The scripts do it (`scripts/env.sh`: Unity Skills ports 8090-8099, `projectPath` match, abort on mismatch). If no Editor matches, report which
  routes you probed before asking anything. Never kill, restart or focus an Editor. Never drive an Editor of another project or checkout.
- **Long runs notify you.** `sweep.sh` and `build-install.sh` take minutes to an hour+. Start them with `run_in_background`, say how long you expect, and wait for the completion notice;
  do not poll and do not make the user ask for status.
- **GPU cost comes from the phone.** The Editor only gives the renderer census, CPU markers and hitches.
- **Measure what you ship.** No experimental build, no uncommitted source unless you say so; the validator checks the APK against HEAD.
- **Follow the repo's own rules** (agent rules, `.meta` handling, namespaces). Cutting a visible feature is the user's decision: measure, then ask.

## Editor access

`build-install.sh` and the project checks use **Unity Skills (REST)**, found by `projectPath` (`editor_execute_menu`, `script_get_compile_feedback`, `console_get_stats`). Without that
plugin, build the dev APK with the project's own command, then write what `build-install.sh` would have written: `<perf dir>/out/build-info.json`
(`game`, `build`, `commit`, `dirtyFiles`, `apk`, `apkSha`, `builtAt`) and install the APK with `adb install -r -t`. Everything after the install is plain `adb` and Python.

## 1. Editor pass (renderer census, CPU, hitches) - about 10 minutes

Drive the Editor with the Unity CLI or Unity Skills, in play mode, with the game's own profiling commands (listed in its `techniques.md`): a renderer census (draws per shader, alpha-tested
and blended materials, particle counts), profiler markers for main and render thread, and a hitch listing. Read the reports yourself. If the CPU main/render thread is above about 10 ms or GC
allocations show up, the problem is not the GPU: fix that before shaders. The census gives the candidates for the Android sweep.

## 2. Build and install the Android dev build - 1 to 4 minutes

```bash
bash scripts/build-install.sh "<build id>"      # compile check, the profile's menus.buildAndroid, install, writes out/build-info.json
```
Needs the Android target active in that Editor (reimport takes long). Check before building: the scale multiplier in the scene (profile `stressScale`; 1 = release) is what you intend and
`git status` is what you intend to measure.

## 3. Plain grid: fps of every unit, level and section - plan about 15 minutes per level for 8 units

```bash
bash scripts/sweep.sh grid --levels medium,high,low
```
The level is pinned and automatic step-down is off (profile `runs.grid`). It records fps, average ms, frames over 20 and 33 ms per cell. Run it at release scale and, when asked, at a stress
scale (edit the serialized multiplier, rebuild, run again; the validator refuses a mismatch).

## 4. Cost breakdown per feature - plan about 12 minutes per unit

```bash
bash scripts/sweep.sh ab
```
For every unit: the ms each switch of the profile's list saves, interleaved on/off. `costGroups` in the profile say how switches stack into the chart (overlapping ones are subtracted);
`totalSwitch` is the unit's total to compare the sum against (checks.md item 8).

## 5. Screenshots

```bash
bash scripts/sweep.sh shots     # one per unit -> <perf dir>/out/*.png; keep the good ones as <perf dir>/shots/<unit>.jpg (lower-case unit name)
```
Look at them.

## 6. Validate (sweep.sh does it) and read `reference/checks.md`

`scripts/validate.py` reports MISSING (re-run once automatically), INVALID (dropped from the report, re-run) and NOTES. Work through the by-hand list before using a number.

## 7. Log what changed

```bash
python3 scripts/log_change.py build  --id "<build id>" --desc "what this build contains"          # commit and date are filled in
python3 scripts/log_change.py effect --change "<what>" --kind Shader --effect "<numbers>" --result kept|no|try [--build "<build id>"]
```
Every build gets a `build` entry and every measured optimization an `effect` entry (also rejected ones: `no`, and upper bounds: `try`). An effect without numbers is not logged.
Update `<perf dir>/status.md` (first paragraphs, then `- ` bullets): where it stands, what is left, what is not verified.

## 8. Render

```bash
python3 scripts/render.py --out <perf dir>/out/files/report.html --files-dir <perf dir>/out/files   # also copies <perf dir>/shots/*.jpg
```
Built from the data: fps by unit/level/section (release and stress), stacked cost per unit, changes over the builds, what each optimization did, and the **device-tier matrix** (Low-end /
Mid-range / High-end x the game's levels x release/stress scale: worst fps and slow frames; a tier with no measured phone says "not measured" and is never estimated). The header names the
build and commit of every chart.

## 9. Publish

`Artifact read <url>` first, then `Artifact` with `file_path` = the rendered html and `url` = the profile's `artifact` (a new path makes a new link); the screenshots go as `files`
(`shots/<unit>.jpg`). If you cannot edit the artifact, publish a new one and say so. The report is a plain HTML page: any static host works too.

## Measuring another phone (the tier matrix)

1. Connect it; `ADB="adb -s <serial>"` if several are attached.
2. Add its model (`adb shell getprop ro.product.model`) to a tier in `<perf dir>/devices.json` (copy `devices.default.json`, fill `models`).
3. Install the same APK, run steps 3 to 6. Records carry the device from the harness' DEVICE line, so the tiers fill themselves.
4. Do not copy numbers between phones. Pin the level for the matrix, and run once unpinned to see where the game's automatic step-down lands.

## Files of the skill

- `scripts/`: `env.sh` (paths, Editor discovery, adb), `gameprofile.py` (finds the perf folder and profile), `stress.py`, `build-install.sh`, `device-run.sh`, `sweep.sh`, `record.py`,
  `validate.py`, `log_change.py`, `render.py`.
- `templates/report.html.tpl` (game-neutral page; `render.py` fills it from the data and the profile), `devices.default.json` (default tiers).
- `examples/`: `profile.example.json`, `DeviceRun.skeleton.cs` (a harness skeleton following the protocol).
- `reference/`: `editor-profiler.md`, `device-gate-and-loop.md`, `techniques.md`, `checks.md`, `harness-protocol.md`.
