# Editor Profiler capture: extract, read, rank

The Editor profile is **dev-machine CPU only**. It finds hot code, allocations and hitch causes. It is never the device fps gate (see `device-gate-and-loop.md`).

## Get a `.data` capture into JSON

Pick the first that your project has:

1. **Project extractor** (an Editor script exposing e.g. `ProfilerDataExtractor.ExtractFile(dataPath, jsonPath)`): call it through the Unity CLI `eval` or a Unity Skills execute-menu call. It is
   asynchronous: start it, then poll for the output file (5-120 s for large captures). Never walk a Deep tree inside a blocking call.
2. **Pipeline/CLI commands** your project registers (e.g. `profiler_capture`, `profiler_extract_file`), if any: `unity command ... ` and poll the session file they write.
3. **Menu fallback**: a menu item that extracts the latest capture.

If the project has none of these, write a small Editor script that loads the capture with `ProfilerDriver.LoadProfile`, walks frames with `ProfilerDriver.GetHierarchyFrameDataView`, and writes the
JSON below (limit depth to about 6). Keep it in the game's repo, not in this skill.

Prerequisites: the Editor of this project is open and ready (`env.sh` finds it by path). Stop play mode before code edits; recompile and check the console afterwards.

## JSON export

| Section | Meaning |
|---|---|
| `stats` | avg / median / p95 / p99 / max / min frame time (ms) |
| `spikes` | frames >= 20 ms |
| `topByTotalTime` | cumulative time including children (top 80) |
| `topBySelfTime` | self time excluding children (top 50) |
| `topGC` | GC allocation hotspots (top 50) |
| `spikeDetails` | per-sample breakdown of the 5 worst spike frames |

Entry: `{"n":"Name","t":41.03,"s":2.57,"gc":0,"c":18258,"fr":899,"mx":0.32}` = name, total ms, self ms, GC bytes, calls, frames present in, max single-frame ms.

## Quick metrics and priority

```
gcBytesPerFrame = topGC[0].gc / totalFrames
selfPerFrame    = entry.s / entry.fr
callsPerFrame   = entry.c / entry.fr
priorityScore   = selfPerFrame * min(callsPerFrame, 1000) + gcBytes * 0.01 / totalFrames      (rank fixes with score > 50)
```
Check `gcBytesPerFrame` first: a regression there is the cheapest signal.

## Decision tree

```
Spike issue (p99 high or spikes[] not empty)?
  YES -> spikeDetails[], self time first
    Semaphore.WaitForSignal / Gfx.WaitForPresent -> display / GPU bound (lock refresh rate, then cut fill). Do not micro-optimize Update.
    GC.Collect                                   -> reduce upstream allocations
    Instantiate                                  -> pool / preallocate
    Loading                                      -> async load, spread over frames
    Shader.CreateGPUProgram                      -> warm the needed variants (not WarmupAllShaders on the measured path)
    Profiler.* / ProfilerWindow.*                -> profiler overhead: close the Profiler window
  NO  -> topBySelfTime[]
    t/fr > 0.5 ms -> optimize the loop body
    c/fr > 100    -> cache the result or call less often
```
Present-bound fingerprint: median about 16.7 ms (holding 60 Hz) with p99 about 33 ms (2x vsync). Rank hitch self time; if wait-for-present dominates, stop tuning CPU code.

## Red flags

| Pattern | Problem | Fix |
|---|---|---|
| high `c`, moderate `s` | called too often | cache or reduce frequency |
| high `gc` in game code | allocating per frame | pool / cache / struct |
| `Delegate.Combine` in GC | event subscription leak | subscribe once |
| `mx` >> `t/fr` | occasional spike | find the expensive path |
| wait-for-present dominates hitch self time | present / GPU wait | refresh lock, then fill |

## Editor loop (max 5 iterations)

```
1. stop play   2. compile and wait   3. console: zero errors (else stop)   4. capture (about 15 s of gameplay)   5. extract, wait for the file
6. analyze (decision tree + red flags)   7. top score > 50 and fixable -> one fix, back to 1; else exit
```
Exit on: nothing above threshold, plateau (same numbers after a real change), 5 iterations, or a compile error you cannot clear.

## Report format

1. Session overview (`stats`, `gcBytesPerFrame`, spike count)  2. entries for the subsystem asked about (filter by name)  3. root cause of the worst spikes (self-time ranked)
4. ranked fixes with scores  5. a re-capture recipe if the workload was not exercised

## Safety

Never edit `Library/PackageCache/`. A deeper walk of a subsystem may fail inside the Editor evaluator sandbox; fall back to marker names from the export.
