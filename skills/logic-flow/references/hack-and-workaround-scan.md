# Hacks, workarounds, and second clocks (mandatory)

The flow map exists so a human can **reject** a path. If a workaround is only in a `verify` tooltip, it was not assessed.

Agents omit these because they look like helpers. They are not helpers. They change whether a note can die, attach, or play.

## Never bury these in `verify` only

Each item below is an **ACTION** (or a PROCESS tick step plus an outgoing **edge**) on the journey spine.

| Kind | What to look for | Show as |
|------|------------------|---------|
| Second clock | `*Until`, `*Grace`, `*IgnoreBefore`, extra deadline besides cut T | Own ACTION: what it arms, when it expires, which notes it covers |
| Parallel ignore | Miss/attach blocked by Mode **and** a time window | Edge per gate (`Mode is None so grace does not apply`) |
| Recover + reschedule | `ResetGameplay` then `ScheduleMissCheck` on the died note | Own ACTION after rewind/end; say the tile is `None` again and can remiss |
| Defer flag | `Defer*`, `FlashBefore*`, wait-then-complete | ACTION on the spine (`SetDeferDeathRevive` → later `CompleteDeferred…`) |
| Recut / second apply | Same cut function on Die and on BeginRewind | Step or child ACTION: first write vs later no-op re-attach |
| Derived flag | `IsPlaying` computed from state/phase/mode, not assigned | Step on the ACTION that changes GameState/Mode: what `IsPlaying` becomes |
| Teardown restore | `Reset` then write Keep/Cut/grace back | Steps on `EndInterruption`: what survives, what is re-armed |
| Compat / alias | `PullPhase` on a rewind, `ResumeGame` wrapping `ReviveGame` | Use the real method title; edge if a wrapper is skipped |

`verify` is for uncertainty and config. It is **not** a dump for logic the reviewer must judge.

## Scan before writing nodes

Search the journey files for:

`Grace`, `Until`, `Ignore`, `Fallback`, `Compat`, `Legacy`, `Defer`, `Recover`, `Reschedule`, `workaround`, `hack`, `unless`, `just in case`, `temporary`, `Obsolete`, `for now`

Open every teardown (`End*`, `Complete*`, `Reset*Loop*`, `Recover*`). List fields it **clears** and fields it **writes back**. If it writes a clock that is not cut T, that clock is a node.

## Honesty pass (required before `--lint`)

Answer in the flow (node or edge), not in chat:

1. Besides cut T / `GameState`, what other clocks or ignore windows fire on this journey?
2. After recover/reset, can the same note miss again? Show the reschedule.
3. Does a flag stay set (`DeferDeathRevive`) past a state pill? Show the later complete.
4. Does unwind/play use a derived `IsPlaying` so miss delivery turns on early?
5. Did you skip a wrapper (`ResumeGame`) that the tap does not call?

If any answer is “yes, but only in verify” — split a node onto the spine.

## Typical workarounds that must be spine nodes (do not drop)

- A second timer or clock armed while the first one already exists (`ignoreUntil = anchor + delay` next to an existing cut).
- A grace window that is active only during one transition mode and does nothing afterwards except expire.
- A recover step that resets state and then re-schedules the same work (reset + re-arm).
- A derived "is playing" flag that is true in a state where delivery should be blocked.
- A shortcut entry point that calls a different router than the one the user path implies (for example Revive calls `ReviveGame` directly; `ResumeGame` is a different router).

## Anti-patterns

| Wrong | Right |
|-------|--------|
| Merge grace into `CompleteUnwind` step 5 | `Arm resume miss grace` ACTION + edge `keep-cluster until anchor+depart` |
| `verify recover resets died tile` | `RecoverDieRewindNote` ACTION on the spine |
| Skip `ResumeGame` because “it just calls ReviveGame” | Show the tap ACTION that calls `ReviveGame`; `verify` that the other router is not on this path |
| “Follow calls only far enough” and stop at `EndInterruption` | Read the body: resets, restores, second clocks, recover |
