# Logic Flow text format

Line-oriented, diff-friendly. Fields separated by `|`; blank lines and `#` comments ignored.

```text
flow init | 01 · Init + views | Core boot and presentation attachment
node boot | EnsureCore | - | AppContext.Initialization.cs | verified | checkpoint
step boot | 1. Start the state machine in APP_NONE.
node none | APP_NONE | - | AppContext.Initialization.cs | verified | checkpoint
node init | InitGame | - | AppContext.Api.cs | verified | checkpoint
step init | 1. Validate prerequisites and mark the context initialized.
node inited | APP_INITED | - | AppContext.Api.cs | verified | checkpoint
edge boot -> none | state machine constructed
edge none -> init | InitGame called
edge init -> inited | validation succeeds
end
```

Notice: **arrival at `APP_INITED` is an edge**, not a node titled `APP_NONE to APP_INITED`.

## Grammar

- `flow <id> | <title> | <description>` — one journey or reference table per flow.
- `node <id> | <title> | <brief> | <source> | <certainty> | <kind>`
  - `brief` may be a string, JSON string array, or `-` (no header line; steps only).
  - `certainty`: `verified` | `inferred` | `runtime`
  - `kind`: `checkpoint` (discrete step) | `process` (runs every frame until an edge fires)
- `step <node-id> | <one plain sentence>` — appends one line; use for numbered action lists.
- `story <node-id> | <user-visible reason>`
- `verify <node-id> | <one short verification fact>` — repeat for multiple hints; **never** one paragraph with several facts. Do not use `verify` as the only record of a workaround, second clock, or recover+reschedule — those need a node or edge (see hack-and-workaround-scan.md).
- `tone <node-id> | dispatch|callback` — optional visual role for the renderer (purple dispatch entry, amber event callback). Does not change node kind.
- `edge <from> -> <to> | <event, guard, or completion>` — **the only place transitions belong**
- `end` — closes the flow.
- `block <id> | <title> | <description>` … `endblock` — file-scope reusable sub-graph.
- `useblock <local-id> | <block-id> [| note]` — reference a shared block.
- `group <id> | <title> | <description>` … `endgroup` — flow-local sub-graph (inside one `flow` only).
- `usegroup <local-id> | <group-id> [| note]` — reference a local group.

No field text may contain `|` (parser splits on it).

## Node card layout (rendered)

Every node renders as four bands separated by horizontal rules:

```text
[TITLE]                         (process spinner if kind = process)
Role line 1                     brief field — what this node is for (max 3 lines)
Role line 2
─────────────────────────────
• Detail bullet 1               step lines — logic inside the node (max 5)
• Detail bullet 2               combine trivial steps; split node if >5
─────────────────────────────
AppContext.State.cs          (i)  verify hints as bullet list in tooltip
```

| Band | Source field | Rules |
|------|--------------|-------|
| **Title** | `node` title | STATE name, ACTION name, or PROCESS loop name |
| **Role** | `brief` | Max **3** short lines on the node's purpose. Use `-` when the title alone is enough. Never repeat the title. |
| **Details** | `step` lines | Max **5** bullets. Number in source (`1.` … `5.`); renderer shows bullets. Combine unimportant steps. |
| **Footer** | `source` + `verify` | Filename only. One short fact per `verify` line. |

STATE nodes: title + footer only (brief `-`, no steps).

Routing ACTION nodes: title + footer only (brief `-`, no steps; guards on edges).

PROCESS nodes: title + spinner + role (optional) + detail bullets describing one tick.

## Node anatomy (authoring fields)

| Field | Purpose | Rules |
|-------|---------|-------|
| **title** | What this node **is** | STATE name, ACTION verb phrase, or PROCESS loop name. **Never** `A to B`. |
| **brief** | Role summary (top band) | Max **3** lines. What this node is for — not how. Use `-` when title is enough. |
| **step** | Detail bullets (middle band) | Max **5**. Numbered `1.`–`5.` in source; combine trivial work. Split node if more needed. |
| **source** | Code file | **Filename only** (`AppContext.State.cs`). No path, no line numbers. |
| **verify** | Verification hint | **One short fact per `verify` line.** No paragraphs. Use multiple `verify` lines instead of one long block. |

## Three node kinds only

Every node is **STATE**, **ACTION**, or **PROCESS**. No other kind exists.

### STATE

- Title = exact state enum (`APP_PLAY`, `APP_REWIND`; or `TileStatus.None` when the graph tracks tile status).
- `brief` = `-`. No steps (dwelling in a state is not work).

### ACTION

Two shapes; both use `kind` = `checkpoint`:

1. **Work action** — title = what runs (`Apply pause note cut`, `DetachAll`). **At most five** numbered `step` lines. If the code does more than five distinguishable effects, **split into chained ACTION nodes** linked by edges (`resolve keep line` → `purge below keep` → `notify listeners`).
2. **Routing action** — title = entry/dispatch (`PauseGame`, `ResumeGame`, `Ready gate`). `brief` = `-`, **zero** `step` lines. Every guard is an outgoing `edge`. Still ACTION, not a separate type.

Do **not** write "set state to APP_PAUSE" as a step when the next node is `APP_PAUSE` — the STATE node plus edge carry the transition.

### PROCESS

- `kind` = `process`.
- Title = loop name (`Tick fast-forward seek`, `Pull phase tick`).
- Steps = one frame/tick of work. Exit via edge when loop completes.

## Reusable blocks (sub-graphs)

When the same sequence appears in two or more flows, define it **once** as a file-scope `block` and reference it with `useblock`.

When a sequence is long but only used in one journey, define a flow-local `group` and reference it with `usegroup`. Groups collapse the same way as blocks (green card, vertical column when expanded) but stay inside that flow.

```text
flow start | 01 · Start to playing | ...
group checkpoint_ff | Checkpoint fast-forward | Seek clock to anchor, attach tiles, branch to prepare or play
node beginff | BeginFastForward | - | AppContext.FastForwardWindow.cs | verified | checkpoint
node tickff | TickFastForward | - | AppContext.FastForwardWindow.cs | verified | process
node ffcomplete | CompleteFastForward dispatch | - | AppContext.FastForwardWindow.cs | verified | checkpoint
edge beginff -> tickff | fast-forward active
edge tickff -> ffcomplete | seek reaches anchor
endgroup

usegroup ff | checkpoint_ff | Checkpoint skip only; normal start tap bypasses this group.
edge ffguard -> ff | checkpoint request proceeds
edge ff.ffcomplete -> play | autoPlay with zero prepare
end
```

Shared blocks use the same mechanics with `block` / `endblock` / `useblock` at file scope.

```text
block delta_unwind | Unwind prepare delta to play | Consume prepare delta, then restore forward playback
node u_enter | Enter delta unwind | - | AppContext.State.cs | verified | checkpoint
step u_enter | 1. Set phase to DeltaUnwind and mark rewinding inactive.
node u_tick | TickDeltaUnwind | - | AppContext.State.cs | verified | process
step u_tick | 1. Decrease prepare delta each frame with speed scaling and cap.
node u_done | Complete delta unwind | - | AppContext.State.cs | verified | checkpoint
step u_done | 1. Clear prepare delta, phase, and blocked attach notes.
edge u_enter -> u_tick | unwind started
edge u_tick -> u_done | delta reached zero
endblock

flow pauseresume | 02 · Pause to resume | …
node rewind | APP_REWIND | - | AppContext.State.cs | verified | checkpoint
node play | APP_PLAY | - | AppContext.Api.cs | verified | checkpoint
useblock unwind | delta_unwind | Rewind exit state is APP_PLAY for a resume scroll.
edge rewind -> unwind | delta unwind active
edge unwind -> play | enter APP_PLAY
end
```

### Ports

- `edge x -> unwind` enters the block's **entry** nodes (those with no inner incoming edge).
- `edge unwind -> y` leaves from the block's **exit** nodes (those with no inner outgoing edge).
- `edge unwind.u_done -> y` / `edge x -> unwind.u_done` addresses **one inner node** when a caller skips or interrupts mid-block (`ref-id.inner-node-id`).

Collapsed, a `ref.inner` edge folds onto the block card and identical from/to/label pairs are deduplicated. Expanded, it attaches to that exact inner node.

### Rendering

- **Collapsed** (default): one layered card — block title, the `useblock` note (or block description), inner node titles as bullets, `block · N` badge, and `open ↗`.
- **Expanded**: the toolbar `⊞ expand blocks` toggle inlines every block in the current flow. Inner nodes stack **vertically in one column** with a bordered frame around the group; the main flow still advances left-to-right between columns.
- **Standalone**: `open ↗`, a double-click on the card, or the drawer's *Shared blocks* section opens the block as its own vertical column diagram, with `‹ back to flow` to return.

### Rules

- Extract a block only when the sequence is **the same code path** in every caller. If one caller's branch does extra work (a death-cause variant, for example), keep that caller explicit and note the difference on a `verify` line in the block.
- A block needs at least two nodes and at least one caller; lint flags unused blocks.
- Keep caller-specific facts in the `useblock` note, not in the block body.
- Blocks may reference other blocks; a block may not reference itself.
- Lint reports any node-title triple that repeats across flows as a block candidate.

## Step style

Write for a human verifying logic, not for the compiler:

- **Good:** "Purge every chart tile before the died note."
- **Bad:** `if (!_isRewinding) return;`
- **Bad:** "Transition to APP_PLAY." (use edge + state node instead)

Keep domain vocabulary: `APP_*`, `TileStatus.*`, `RewindCause.*`, `RewindWindowPhase.*`.

## Edge style

Edges answer **why execution moves here**.

- Guard: `chart has at least one note`, `already fast-forwarding`
- Event: `player pauses`, `miss check fires`
- Completion: `pull complete`, `prepare delta reaches zero`
- State entry (when target is a state node): `enter APP_PLAY` is acceptable on the edge label if the cause is otherwise unclear

Converging paths may share a destination; keep labels distinct.

## Anti-patterns (reject on lint)

| Anti-pattern | Fix |
|--------------|-----|
| Node titled `APP_A to APP_B` | Split into state nodes `APP_A`, action(s), `APP_B`; put cause on `edge` |
| Brief repeats title | `brief` → `-` |
| First step repeats title or brief | Remove duplicate; keep one |
| Routing ACTION with `step` lines | Delete steps; move each guard to an `edge` |
| Step says "transition to …" | Delete step; add state node + `edge` |
| Parent step restates child an edge names | Delete parent step |
| Branch only in prose inside a node | Add `edge` + child node |
| More than five `step` lines on one node | Split into chained ACTION nodes; max five steps each |
| Source includes line numbers or path | Filename only, e.g. `AppContext.State.cs` |
| One long `verify` paragraph | Several `verify` lines, one fact each |
| Same sequence copied into several flows | Define one `block`; `useblock` it from each flow |
| Block declared but never used | Inline it back into its flow, or delete it |
| Caller-specific detail written into a block node | Move it to the `useblock` note or the caller's own nodes |
| `No state change`, `noop`, `*_noop`, or title ending in `noop` | Delete node; put each suppressed path on `verify` of the owning ACTION; drop dead-end edges |

## Extraction vs layout

Do not add x/y coordinates. The renderer auto-layouts from structure and content height.
