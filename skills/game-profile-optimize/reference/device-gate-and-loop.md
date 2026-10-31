# Device gate, classification and the improve loop

## Two tracks, never mixed

| Track | Where | Gate truth |
|---|---|---|
| Editor play | Profiler + Editor extract | dev-machine CPU only (`editor-profiler.md`) |
| Android device | development APK + adb + on-device harness | **Final, profiler off**, gameplay frames only |

Never gate on Deep / ProfilerFile / Editor medians (inflated or wrong hardware). Never treat Editor fps as device truth.

## Capture modes

| Mode | Use |
|---|---|
| DeepProfile | marker names and hierarchy (times inflated) |
| ProfilerFile | `.data` + timeline for hitch classification |
| FinalNoProfiler | **the only mode that counts as the gate** |

Measure at 1x simulation and audio speed. Lock the panel to the gate Hz once at boot; do not call `Screen.SetResolution` every N frames (display renegotiation causes stalls).

## What to measure (device Final)

Gameplay frames only, at least 60 after warm-up, frame time in ms. Solid-60 gate: median <= 16.9, p99 <= 20, max <= 22 (fps = 1000 / ms; report both).
Reject the run if it reports `heartbeat`, `ui_only`, `no_gameplay_frames`, `aborted` or fewer than 60 gameplay frames. Wait for the gate file's **timestamp**, not only a status string (`building`/`error` can race).

## Classify from hitch self time

On ProfilerFile / Deep, rank self time on gameplay frames >= 20 ms (not total time, not boot or UI frames).

| Dominant markers | Bound | First actions |
|---|---|---|
| `Semaphore.WaitForSignal`, `Gfx.WaitForPresent`, camera-stack render markers with light scripts | GPU / present | confirm the Hz lock; cut fill (render scale, particles, extra cameras and copies) |
| scripts, `Canvas.BuildBatch`, `GC.Collect`, `Instantiate`, layout rebuild | CPU | pool, debounce layout, strip player `OnGUI`, cut per-frame allocations |
| `Shader.CreateGPUProgram` | shader compile | warm the needed variants at preload (a prefab pool prewarm does not warm GPU programs) |

Rule: p50 about 16.7 ms with p99 about 33 ms (exactly 2x vsync) = missed vsync / present wait. Do not micro-optimize `Update`. A modest fill cut (render scale 0.85) often does not break a 2x vsync hitch; the next
lever is a large fill cut or fewer passes, after the refresh rate is locked.

## Improve loop: one hypothesis per Final

```
1. Final gate   2. FAIL -> ProfilerFile extract (markers)   3. classify the bound -> ONE change that ships (not a harness-only cheat)
4. append session entry #N   5. one Final rebuild   6. compare p50 / p99 / max with the previous entry; plateau -> new hypothesis
```
Ladder when present-bound: refresh and target frame rate locked once -> device-tier quality (render scale, particle caps, skip looping ambient VFX) -> extra camera stacks and full-screen copies (measure first)
-> targeted shader warm -> then CPU. Same gate for 3+ Finals with no metric move: stop. Builds are not progress.

## Session log (the host writes it, not the model)

One block per iteration, no poll spam:

```markdown
# N - YYYY-MM-DD HH:MM - PASS|FAIL|DIAG - Final|ProfilerFile
## Metrics        | scope | source | frames | avg ms | p50 | p95 | p99 | max | fps p50 | fps p99 |
## Analysis       bound (GPU / CPU / shader), what dominated
## Assumptions    why the change might help
## Changes        | file | change |
## Next
```
Here that is `scripts/log_change.py` and `runs.ndjson`; for a longer unattended loop let a host script (Python) own the loop: trigger capture -> wait for the gate file -> collect metrics -> spawn one
worker for one fix -> append the log -> next Final. A chat agent must not poll status or append the log. A `STOP` file in the perf folder ends the loop after the current iteration.

## Gates around every worker and measurement

G1 Editor ready (found by project path). G2 compile and wait. G3 console shows zero errors. G4 Unity Skills `/health` answers on this project's port. G5 optional project wiring (menus or checks the profile
lists). Do not advance a loop iteration, and never run a measurement, while G2-G3 are red. On failure keep the Editor.log tail and the gate JSON next to the run.

## Android device preparation (every install)

```bash
adb -s $SERIAL shell svc power stayon true
adb -s $SERIAL shell settings put system peak_refresh_rate 60       # use the gate Hz; a 90 Hz panel with a 60 target gives about 33 ms waits
adb -s $SERIAL shell settings put system min_refresh_rate 60
adb -s $SERIAL shell settings put secure refresh_rate_mode 0
```
The harness sets `Application.targetFrameRate` to the gate Hz with `vSyncCount = 0` once at boot.

## Harness must-haves

- It starts gameplay on its own, with an **offline fallback** content item baked into the build (a reinstall loop must not depend on a network catalog, or you get `ui_only` / `no_gameplay_frames`).
- Measure only gameplay frames after warm-up; drop boot and menu frames.
- A fresh game per unit; a shared session can end partway and later units render an empty scene.
- Never ship harness-only hacks that change what is measured.

## Build pitfalls

- Only one Unity major version's licensing client per machine; a second one makes `BuildPlayer` return `Unknown`. Do not kill editors to fix it: report it.
- Stop play mode before `BuildPlayer`. Compile errors mid-build give `Unknown` too. Read Editor.log.
- Android target must already be active (reimport takes long).

## Common failures

| Symptom | Cause | Fix |
|---|---|---|
| `Build failed: Unknown` | licensing conflict, play mode, compile errors | see Build pitfalls |
| `ui_only` / `no_gameplay_frames` | no catalog offline, start never called | bake the fallback content; read the harness tag in logcat |
| median 16.7, p99 33 | refresh-rate mismatch | lock the panel Hz, once at boot |
| home or boot wait timeout | init blocked offline | extend the wait or skip home when the fallback is ready |

## What not to do

| Anti-pattern | Why |
|---|---|
| gate on Deep / ProfilerFile / Editor play | inflated or wrong hardware |
| a chat agent owns the session log or polls forever | missing or spam blocks |
| automatic re-loop without analysis | rebuild spam on the same p99 |
| harness-only GPU hacks that never ship | the gate lies |
| `Screen.SetResolution` during gameplay | renegotiation causes stalls |
| `Shader.WarmupAllShaders` on the measured path | multi-second boot, rarely moves p99 |
| physics "query-only" hacks (script simulation mode, no collision detection) | raycast and tap input dies on device |
| disabling overlay UI cameras as a default GPU cheat | breaks the shell UI |
| dropping features or quality without the owner's consent | use a production device-tier policy instead |
