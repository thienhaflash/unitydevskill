# Extracting code into a human-verifiable graph

## Start with the journey, not the codebase

Write one sentence: **"While [phase], [event] → [recovery] → [steady state]."**

Good flow list (rhythm / interruption example):

1. Start → fast-forward → prepare scroll → playing
2. Playing → pause → resume → pull up → playing (repeat)
3. Playing → miss → rewind → revive → pull up → playing
4. Playing → wrong tap (two detectors) → shared death pipeline → playing
5. Playing → seek → playing or paused
6. Playing → near end of round → next round → playing

Bad flow list: "predicates", "PauseGame API", "miss-check module" — those are reference tables, not journeys.

For each journey identify:

- entry state and trigger;
- **STATE nodes** along the spine;
- **ACTION nodes** between states (cuts, detaches, dispatch entries, scheduling);
- **PROCESS nodes** for per-frame loops;
- exit state or return to steady play;
- branches to **omit** because another journey owns them.

## Repository scan

Search entry events, state assignments (`GameState =`), and side-effect verbs first: `Pause`, `Resume`, `Die`, `Seek`, `Purge`, `Detach`, `Reset`, `Schedule`, `Recover`, `Defer`, `Grace`, `Until`, `Ignore`. Trace the smallest chain between **state writes**. Then open teardown bodies (`EndInterruption`, `CompleteRewind`, `RecoverDieRewindNote`) even if they look like helpers. Cross-check tests and config. Read [hack-and-workaround-scan.md](hack-and-workaround-scan.md).

Classify every claim:

- `verified` — direct source anchor;
- `inferred` — reasonable from context, not proven;
- `runtime` — needs device/build/config check.

## Graph shape: states, actions, edges

The spine should read as a **timeline of where the machine is and what runs between states**.

```
[APP_PLAY] --player pauses--> [Apply pause note cut] --cut done--> [APP_PAUSE]
```

Not:

```
[APP_PLAY to APP_PAUSE]  step: transition to APP_PAUSE
```

### What to include

- Every **GameState assignment** as arriving at a **state node** via an **edge** (through action nodes if work happens first).
- Side effects that change verification: note cuts, tile purge/detach, miss-check schedule/clear, **recover+reschedule**, anchor fields, deferred flags, **any second clock or grace/ignore window besides cut T**.
- Gates that change the path — as **routing ACTION** nodes (no steps; edges only) or as edges leaving a STATE node.
- Per-frame loops until a completion edge — as **process nodes**.
- Converging entry paths (e.g. two wrong-tap detectors) → one shared pipeline **action** node.
- `verify` for ordering risks, config branches, display-only vs logic time, stale keys across loops.

### What to exclude

- Helper methods that do not change observable state or side effects. A function that arms `*Until`, recovers a died note to `None`, or reschedules miss **does** change outcomes — include it.
- Branches **provably dead** in this journey — note in `verify`, do not expand.
- Resume-from-`APP_REVIVE` inside the pause journey (different journey).
- Reference predicate tables inside a journey — link to appendix flow 07–09 instead.
- Raw code syntax in steps.
- Transitions as node titles or as steps.

### When a function has many branches

1. Is this branch reachable in **this** journey? If no → omit or single no-op node.
2. Is it a guard on entry? → **routing ACTION** node (zero steps) or edge from current STATE; one edge per outcome.
3. Is it work before a state change? → **work ACTION** node with steps, then edge to **STATE** node.

## Factor shared sequences into blocks

After the journeys are drafted, look for the same chain appearing twice. In the rhythm example the prepare scroll (`pull phase → pull completion → delta unwind → APP_PLAY`) runs in start, resume, revive, and wrong-tap revive — one `block` per phase, referenced four times.

1. Confirm it is the **same code path**, not a look-alike. Same functions, same order.
2. Where callers differ only in inputs (rewind cause, exit state, anchor), put that in the `useblock` note.
3. Where a caller's branch does extra work, leave that caller's nodes explicit and record the difference on a block `verify` line. A death-cause pull that also recovers the died note is *not* the same block.
4. Wire skip and interrupt paths with `edge ref.inner -> target`, so a caller that jumps straight to pull completion, or pauses mid-pull, still reads correctly.
5. `--lint` names repeated node-title triples; treat each as a block candidate to accept or justify.

## Node and edge quality

**Merge** when: sequential helpers with no user-visible checkpoint between them, **and** none of them is a second clock, defer flag, recover+reschedule, or Mode-gated ignore.

**Split** when: a guard changes the path; a state is assigned; a side effect must be verified alone; a per-frame loop begins or ends; **an ACTION would need more than five steps** (chain smaller ACTION nodes instead).

**Edge labels** must be readable without opening the node: `deferral fired`, `prepare time is zero`, `was not playing`.

**No no-op nodes.** Do not model early returns or guard failures as nodes (`No state change`, `noop`, `PrepareScroll_Freeze noop`, etc.). Record each suppressed path on `verify` lines of the ACTION that owns the branch. Omit the dead-end edge from the graph.

## Human verification checklist

- Does this branch occur with real content/config?
- Is ordering guaranteed or incidental?
- Does cleanup run on cancel/failure?
- Display time vs song time (rewind pull, fast-forward)?
- Do loop-scoped cut keys survive rollover incorrectly?
- Does a deferred path (wrong-lane deferral) differ from immediate path (swipe punish)?
- Is there a second miss/attach clock besides cut T? If yes, it must be a node, not a tooltip.
- After recover, can the same keep-from note remiss in APP_PLAY? Show that ACTION.
- Derived flags (`IsPlaying` from state/phase/mode) — does miss delivery turn on during unwind?

## QA before handoff

```bash
python3 <skill dir>/scripts/extract_flow_data.py journey.flow --lint
python3 <skill dir>/scripts/extract_flow_data.py journey.flow -o /tmp/check.json
```

Lint must report zero errors. Warnings should be fixed or justified in `verify`.
