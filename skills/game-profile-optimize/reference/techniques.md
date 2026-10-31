# Techniques for profiling Unity games on Android

Game-independent. What a particular game adopted or rejected belongs next to its profile (`<repo>/.claude/perf/<game>/techniques.md`), not here.
Numbers quoted as examples come from one low-end phone (Adreno 610, Vulkan, 1080x2408 @60 Hz) in a 3D rhythm game.

## What decides cost on this class of GPU

- Adreno is tile-based. A fragment shader that can `discard` / `clip` loses early depth rejection (LRZ), so every overlapping tree, rock and wall pays its full
  fragment cost. That was the largest single cost of the scenery in the example game.
- Fragment cost scales with pixels: the stress scale 1.3 means 1.7x the pixels of scale 1.0.
- GPU time alone does not give 60 fps: two scenes ran 52 fps at about 16 ms GPU. Plan for about 14 ms.
- Frame pacing: Android's optimized frame-pacing library (Swappy, Unity Player setting `androidUseSwappy`) caused a frame-pacing problem in one game and was turned off; check it on any new game.

## Measurement and process methods

- **Interleaved A/B on the device** through intent extras (`ab=`): switch on and off several times inside one run, so thermal drift cancels. Plain A-then-B runs drift.
- **Pin everything**: the quality level, no automatic step-down, one fresh game per unit, a fixed seconds per section, the same section for A/B. Record device, GPU, resolution, quality line.
- **Provenance in every record**: build id, commit, dirty flag, APK hash (`out/<game>/build-info.json`). A number without a build is not a result.
- **Editor for the renderer census and CPU markers only** (the game's own Editor profiling commands; see its notes); GPU cost comes from the phone (the Editor GPU and Mac Metal are not the phone).
- **Find the Editor of this checkout by path.** Several Editors run at once. Unity Skills ports 8090-8099, match `projectPath` to the project folder (the answer can carry a suffix such as `/Assets`). Never the default CLI port blindly, never by project name. Never kill, restart or focus an Editor (focus steals the user's window).
- **An old Unity Pipeline/CLI package in the Editor may not parse `console` / `eval` command lines** (it said so: update to a newer version); Unity Skills REST (`script_get_compile_feedback`, `editor_execute_menu`, `console_get_stats`) is the fallback.
- **Agent sandboxes**: a worktree-isolated or sandboxed agent session may refuse complex shell (chained git, computed `cd`, eval strings, `sleep` chains). Put logic in scripts, run plain commands, use
  `run_in_background` and wait for the notice instead of polling.
- **Follow the repo's own rules** (agent rules, `.meta` handling, namespaces). The harness is a dev tool behind a scripting define; game code stays clean.
