# Authoring contract (reusable worker prompt)

Copy this block when delegating one journey to a worker. Replace bracketed placeholders.

```text
Read the logic-flow skill and references (graph-format.md,
extraction-workflow.md, authoring-contract.md, hack-and-workaround-scan.md).
Write ONE file:
[path/to/journey.flow]

Journey: [one sentence, chronological, e.g. "while playing, pause -> resume -> pull up -> playing"]

Scope:
- Entry: [state + trigger]
- Exit: [steady state]
- OMIT: [branches owned by other journeys]

Sources: [File.cs paths with line ranges if known]

## Graph model (non-negotiable)

Three node kinds only: STATE, ACTION, PROCESS.

1. STATE — title is the state name only (APP_PLAY). brief = -. No "A to B" titles.
2. ACTION — title is a verb phrase. Two shapes:
   - work action: steps list effects (Apply pause note cut).
   - routing action: brief = -, NO step lines; every guard is an edge (PauseGame, Ready gate).
   Routing is still ACTION, not a fourth kind.
3. PROCESS — kind = process. Per-frame loop until a completion edge fires.
4. TRANSITIONS — edges ONLY. Never in a node title or step. Example:
     edge play -> pause_cut | player pauses
     edge pause_cut -> paused | note cut complete
   where play=APP_PLAY (STATE), pause_cut=ACTION, paused=APP_PAUSE (STATE).

## Node card layout (what the reader sees)

[TITLE] (process icon if process)
brief role — max 3 lines, what this node is for
─────────────────
• detail bullets — max 5 step lines, how the logic runs
─────────────────
File.cs (i)

- `brief` = role band. `-` when title is enough.
- `step` = detail band. Number 1–5 in source; combine trivial steps.
- Never repeat title in brief or first step.

## Anti-duplication

- brief = - when title or steps already say it.
- Never: title + brief + step all saying "start state machine in APP_NONE".
- Never: step "transition to APP_X" — use edge to state node APP_X.

## Step style

Plain English. One numbered action per line, **1–5 only**. No if/return/code syntax.
Keep: APP_*, TileStatus.*, RewindCause.*, RewindWindowPhase.*.
Source: filename only (AppContext.State.cs). No line numbers.
Verify: one short fact per verify line; use multiple verify lines, not paragraphs.

## Structure

- Branch = edge, never a step inside a routing ACTION node.
- Parent must not restate what a child edge already names.
- **No no-op nodes.** Early returns, guard failures, and suppressed outcomes are **not** nodes. Put each fact on a `verify` line on the nearest ACTION that owns the branch. Do not create `No state change`, `noop`, `*_noop`, or title-ending-`noop` nodes; do not add dead-end edges to them.
- One journey per flow; dead branches → verify, not expanded subgraph.
- Two entry detectors → converge on one shared pipeline action node.

## Hacks must be on the canvas

Read hack-and-workaround-scan.md. Do not classify these as "implementation detail":

- Second clocks (`*Until`, `*Grace`, ignore windows other than cut T)
- Recover that ResetGameplay + ScheduleMissCheck (same note can remiss)
- Defer flags completed later (`DeferDeathRevive`)
- End/Complete that Reset then write fields back
- Derived IsPlaying / miss delivery during unwind
- Wrappers the tap does not actually call

Each is an ACTION or an edge. `verify` is not enough. Run the honesty pass in that file before lint.

## Reusable blocks

A sequence that runs in more than one flow is declared ONCE:

  block delta_unwind | Unwind prepare delta to play | Consume prepare delta, restore playback
  node u_enter | Enter delta unwind | - | AppContext.State.cs | verified | checkpoint
  node u_tick | TickDeltaUnwind | - | AppContext.State.cs | verified | process
  node u_done | Complete delta unwind | - | AppContext.State.cs | verified | checkpoint
  edge u_enter -> u_tick | unwind started
  edge u_tick -> u_done | delta reached zero
  endblock

then referenced from each caller:

  useblock unwind | delta_unwind | Rewind exit state is APP_PLAY for a resume scroll.
  edge rewind -> unwind | delta unwind active
  edge unwind -> play | enter APP_PLAY
  edge unwind.u_tick -> mid_pause | pause arrives during unwind

- `edge x -> ref` = block entry, `edge ref -> y` = block exit, `edge ref.inner -> y` = one inner node.
- Caller-specific facts go in the useblock note, not the block body.
- Extract only when it is the SAME code path in every caller. If a caller's branch does
  extra work, keep that caller explicit and note the difference on a block verify line.
- Every block needs ≥2 nodes and ≥1 caller.

## QA

python3 <skill dir>/scripts/extract_flow_data.py [file] --lint
python3 <skill dir>/scripts/extract_flow_data.py [file] -o /tmp/check.json

Report: node count, edge count, block count, lint clean, max 5 steps per node,
filename-only sources, verify as bullet lines, no sequence duplicated across flows.
```

## Journey list template (rhythm / interruption)

| # | Flow title | Spine |
|---|------------|-------|
| 01 | Start to playing | load → APP_READY → optional checkpoint FF → prepare scroll → APP_PLAY |
| 02 | Pause to resume to playing | APP_PLAY → pause/cut → APP_PAUSE → resume → pull → unwind → APP_PLAY |
| 03 | Miss to rewind to playing | miss check → die → APP_REWIND → revive → prepare scroll → APP_PLAY |
| 04 | Wrong tap to playing | ground deferral OR swipe punish → shared wrong-lane pipeline → same as 03 |
| 05 | Seek to playing or paused | immediate seek (DetachAll) OR prepare seek (fast-forward path) |
| 06 | End round to next round | prepare-next-loop → rollover stays APP_PLAY → ClearLoopScopedCutState |

Appendix (optional, not journeys): predicate table, reset matrix, miss-check gate table. Journeys point at them; do not duplicate.

## Common fixes from review

| Problem seen | Fix |
|--------------|-----|
| Node `APP_A to APP_B` | State nodes A and B; action between; edge labeled with cause |
| Edge labels exist but transition also in node title | Remove transition from title; keep edge |
| `Ensure core boot state` + brief + step all say APP_NONE | State node `APP_NONE` + action `EnsureCore` with one step |
| `Ready gate` routing ACTION with step "if no notes…" | Delete steps; edges `chart has no notes` / `chart has at least one note` |
| `ApplyPauseNoteCut` with 8 steps | Split into 2–3 chained ACTION nodes, ≤5 steps each |
| Functional flows ("ResumeGame API") | Reorganize as journey 02 spine |
| Pull/unwind sequence copied into flows 01, 02, 03, 04 | One `block` per phase; `useblock` from each journey |
| `No state change` / `noop` / `*_noop` node | Delete; move facts to `verify` on owning ACTION; remove dead-end edges |
| Grace / Recover / Defer only in `verify` | Promote to ACTION + edge on the spine (see hack-and-workaround-scan.md) |
| Post-back edge to `APP_PLAY` after unwind | Keep edge to `play` in source; renderer creates `play__end` pill automatically |
| Two disconnected subgraphs in one flow | Expected if no edges connect them; renderer shows separate island sections |
