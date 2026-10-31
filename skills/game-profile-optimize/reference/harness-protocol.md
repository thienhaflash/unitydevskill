# Device harness protocol (what a game must implement to be measured)

The scripts are game-independent. A game plugs in with a **profile** (`<repo>/.claude/perf/<game>/profile.json`, see `examples/profile.example.json`) and a **harness**: dev-only code in
its Android build that starts the game on auto-play, runs what the intent extras ask for, and writes the readings to logcat in the line format below. `examples/DeviceRun.skeleton.cs` is a
starting point (untested as a whole; it follows this protocol). Keep the harness behind a scripting define so it is never in release builds or the Editor, and add an Editor builder that sets
the define, builds the APK and writes the result file.

## Build side (profile: `menus.buildAndroid`, `menus.openScene`, `buildResultFile`)

- A menu item that builds the dev APK in the background and writes `buildResultFile`: first line `building`, then `Succeeded ...` or `Failed ...`, with the `.apk` path in the file.
- A menu item that opens the game scene alone (no other scenes loaded).
- Both are reached through Unity Skills `editor_execute_menu` on the Editor of this project, so they work without focusing the Editor.

## Intent extras (`adb shell am start ... --es key value`; `device-run.sh <name> key=value ...`)

Defined by the game's harness and named in the profile's `runs.grid`, `runs.ab`, `runs.shots` templates. Typical ones: pin the quality level, no automatic step-down, seconds per section,
the units to run, the switches to toggle, screenshots. The game chooses its own names; the templates may use `{level}`, `{switches}`, `{unit}`, `{units}`.

## Log lines (all prefixed with the profile's `logTag`, e.g. `MYGAMEPERF`; one `Debug.Log` each)

| Line | Meaning |
|---|---|
| `<TAG> DEVICE <maker> <model> \| <gpu> <api> \| <w>x<h> @<hz>Hz \| quality <level> (<details>) \| kw .. \| scale <s> \| cpu <cpu> \| ram <MB> MB` | once per run: which phone and settings. Tier assignment (`data/devices.json`) keys on `<model>` |
| `<TAG> <unit-id> <Section>: frames N fps X avg Y p50 .. p95 .. p99 .. max .. \| drops>20ms D >33ms E \| cpu ..` | one per unit and section of the plain grid; `fps`/`avg` over the section, `>33ms` = frames over 33 ms |
| `<TAG> AB-RESULT <unit-id> <switch>: off gpu A ms fps B \| ON gpu C ms fps D \| delta E ms` | one per switch of an A/B run; `delta = ON - off` in GPU ms, so cost = `-delta`. Averages over several interleaved on/off blocks |
| `<TAG> SHOT <name>` | the harness is ready for a screenshot; `device-run.sh` calls `adb screencap` ~0.6 s later |
| `<TAG> DONE` / `<TAG> FAIL <reason>` | the run ends; `device-run.sh` stops on either |
| other lines (`SONG`, `THEME`, `HITCH`, `SEC`, `FEAT`, `REPORT`, `STREAK`) | free diagnostics; kept in the raw log in `<perf dir>/out/<name>.txt` |

GPU time comes from the player's frame timings (use `FrameTimingManager`) in a dev build; the Editor's GPU time is not the phone's.

## A/B treatments

Interleaved: switch the treatment on and off several times inside one run, average each side, print one `AB-RESULT`. The off side must be the untreated state (`validate.py`
flags a treatment whose off side differs from the other off sides by more than 1 ms). A treatment is a named switch in one `Treat(name, on)` method; keep the list of switches and what each does
next to the profile (`<perf dir>/switches.md`).

## Profile fields (<repo>/.claude/perf/<game>/profile.json)

`id`, `name`, `project` (Unity project folder, relative to the repo root), `package`, `logTag`, `harness` (path, for humans, optional), `unitLabel` and `units` (id to display name; the
unit is what the game iterates: themes, tracks, levels, maps), `sections` (+ `sectionLabels`), `levels` (the quality levels the game's quality system pins),
`menus.*`, `buildResultFile`, `stressScale` {`file`, `key`, `release`} (a serialized multiplier on the render scale, or omit), `runs.*`, `abLevel`, `switches` (the fixed A/B list),
`costGroups` (how switches stack into the cost chart; `minus` subtracts overlapping groups), `totalSwitch`, `definesCheck`, `page.*` (every game-specific sentence of the report), `artifact`.

## Adding a game

1. Implement the harness above in the game's dev build (start from `examples/DeviceRun.skeleton.cs`; keep it behind a scripting define and out of the Editor), with menu items that open the
   scene alone and build the dev APK (profile `menus.*`, `buildResultFile`).
2. Create `<repo>/.claude/perf/<game>/` with `profile.json` (copy `examples/profile.example.json`), empty `runs.ndjson`, `builds.json` (`[]`), `effects.json` (`[]`), `status.md`, `shots/`,
   optional `devices.json` (override of `devices.default.json`) and a `.gitignore` with `out/`.
3. `bash scripts/build-install.sh`, then `sweep.sh grid`. Everything else (record, validate, render, device tiers) is shared. Commit the perf folder with the game: the team shares the history.
