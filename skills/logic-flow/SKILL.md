---
name: logic-flow
description: Turn codebase behavior into user-story-centered flow graphs using the Logic Flow text format, then render or update an interactive HTML flow for human verification.
---

# Logic Flow

Use this skill when a user wants a visual map of runtime logic, workflows, state transitions, or code-grounded user journeys. The output has two linked artifacts: a plain-text graph source that can be reviewed and diffed, and an interactive HTML flow that supports selecting nodes, following input/output edges, panning, zooming, and collapsing the graph drawer. This is a strict two-stage pipeline: extraction produces data only; the renderer/template produces HTML.

## Workflow

1. Start from **player journeys in time order**, not API areas or file trees. Example spine: `start → fast-forward → prepare scroll → playing`; `playing → pause → resume → pull up → playing`; `playing → miss → rewind → revive → playing`. One flow file = one journey from entry to steady exit (or one reference table).
2. Identify the authoritative state machine (e.g. `AppContext.GameState`). **States are nodes. Transitions are edges.** Actions that run between states are separate action nodes on the path.
3. Scan the repository in this order: entry points and UI/event handlers; state assignments and guards; orchestration between assignments; side effects (audio, tiles, cuts, miss checks); **then the hack scan** in [references/hack-and-workaround-scan.md](references/hack-and-workaround-scan.md). Open every `End*` / `Complete*` / `Recover*` / `Reset*` body. Second clocks, grace windows, defer flags, and recover+reschedule are spine ACTION nodes — not `verify` footnotes.
4. Extract nodes using **only three kinds** in [references/graph-format.md](references/graph-format.md): **STATE**, **ACTION**, **PROCESS**. Attach source anchors; mark claims `verified`, `inferred`, or `runtime`.
5. Extract edges as the **only** place transitions appear. Label with the event, guard, or completion a human recognizes (`chart has no notes`, `pull complete`, `seek reaches anchor`).
6. Record uncertainty in `verify` lines — never in step prose as a hidden branch. Do **not** hide workarounds, fallbacks, or extra ignore clocks in `verify`. Those must be nodes or edges so a human can reject them.
7. **Never author no-op nodes** (`No state change`, `noop`, `*_noop`, titles ending in `noop`). Early returns and guard failures go on `verify` lines of the owning ACTION; drop dead-end edges.
8. Factor any sequence that repeats across flows into a **reusable block** (see below).
9. Write the graph per [references/graph-format.md](references/graph-format.md). Lint with `scripts/extract_flow_data.py --lint` before render.
10. Pass JSON to `scripts/render_flow.py`. The renderer owns layout and interaction.

## Node ontology (mandatory — three kinds only)

Every node is exactly one of **STATE**, **ACTION**, or **PROCESS**. There is no fourth kind.

| Kind | Title | Body | `kind` field | Example |
|------|-------|------|--------------|---------|
| **STATE** | The state name only | `brief` = `-`, no steps | `checkpoint` | `APP_PLAY`, `APP_REWIND` |
| **ACTION** | Verb phrase for what runs here | `step` lines list effects, **or** no steps when the node only routes | `checkpoint` | `SetupSong`, `PauseGame`, `Apply pause note cut` |
| **PROCESS** | Names the per-frame loop | `step` lines describe one tick | `process` | `Delta unwind tick`, `Pull phase tick` |

**Dispatch is ACTION, not a separate kind.** Entry points such as `PauseGame` or `ResumeGame` are ACTION nodes with `brief` = `-` and **zero** `step` lines. Every guard is an outgoing `edge`. Forking never gets its own node type.

**Transitions are edges, never nodes.** Forbidden title form: `APP_A to APP_B`.

**Forbidden:** a node titled `APP_PLAY to APP_PAUSE` or any `A to B` form. That is a **transition** and belongs on an **edge**, not in a node title or step.

Correct pattern:

```text
node play | APP_PLAY | - | ...
node pause_cut | Apply pause note cut | - | ...
step pause_cut | 1. Resolve the keep line and purge tiles below it.
node paused | APP_PAUSE | - | ...
edge play -> pause_cut | player pauses
edge pause_cut -> paused | note cut complete
```

## Node card layout

Rendered top-to-bottom:

1. **Title** + process spinner when `kind` = `process`
2. **Role** — `brief` field, max 3 lines (what the node is for)
3. **Rule** — only when both role and details exist
4. **Details** — `step` lines as bullets, max 5 (logic inside the node)
5. **Rule** — when role or details exist
6. **Footer** — filename + verify tooltip (bullet list)

Authoring: role ≠ steps. Brief answers "what"; steps answer "how". Never duplicate title in brief or first step.

## Reusable blocks and local groups

**Shared block** (`block` / `endblock` / `useblock`) — same sequence in multiple journeys. Blue collapsed card; listed in drawer *Shared blocks*; `open ↗` opens standalone view.

**Local group** (`group` / `endgroup` / `usegroup` inside one flow) — long subsection used only in that journey (e.g. checkpoint fast-forward in journey 01). Green collapsed card; double-click or **⊞ expand sections** to inline; no drawer entry.

Both collapse to one card, expand to a vertical bordered column, and support `ref.inner` edge ports.

```text
block delta_unwind | Unwind prepare delta to play | Consume prepare delta, then restore forward playback
node u_enter | Enter delta unwind | - | AppContext.State.cs | verified | checkpoint
node u_tick | TickDeltaUnwind | - | AppContext.State.cs | verified | process
node u_done | Complete delta unwind | - | AppContext.State.cs | verified | checkpoint
edge u_enter -> u_tick | unwind started
edge u_tick -> u_done | delta reached zero
endblock

useblock unwind | delta_unwind | Rewind exit state is APP_PLAY for a resume scroll.
edge rewind -> unwind | delta unwind active
edge unwind -> play | enter APP_PLAY
edge unwind.u_tick -> mid_pause | pause arrives during unwind
```

- `edge x -> ref` enters the block; `edge ref -> y` leaves its exit; `edge ref.inner -> y` addresses one inner node for skip and interrupt paths.
- Caller-specific facts go in the `useblock` note, never in the block body.
- Extract only when it is genuinely the **same code path**. When one caller's branch does extra work, keep that caller explicit and record the difference on a block `verify` line.
- The reader gets three views: collapsed card (default), `⊞ expand blocks` inlined in the flow, and the block as a standalone diagram via `open ↗` or the drawer's *Shared blocks* list.
- `--lint` reports unused blocks and any node-title triple repeated across flows as a block candidate.

## Anti-duplication

The renderer shows **title + brief + steps** stacked. They must not repeat each other.

- If the title already names the checkpoint, set `brief` to `-`.
- If one step would paraphrase the title, drop the brief or merge — never show both.
- Pure STATE nodes and routing ACTION nodes: `brief` = `-`, no steps.
- A step must never say "transition to APP_X" — the edge to state node `APP_X` already shows that.
- **Max five items per node:** numbered steps 1–5 only. STATE and routing ACTION usually have zero. More work → split the node.
- **Source:** filename only (`AppContext.State.cs`). No `:line` ranges, no directory path.
- **Verify hints:** one short line per `verify` statement; the renderer shows them as a bullet list. Uncertainty and config only — not a hiding place for grace/recover/defer.

Run `extract_flow_data.py --lint` to catch duplicate brief/title, transition-shaped titles, routing ACTION with steps, too many steps, non-filename sources, unused blocks, and repeated sequences that should become blocks.

## Hard boundary

- The extractor emits graph facts only: flows, blocks, nodes, edges, sources, certainty, kind, stories, verification. No x/y, CSS, SVG, or HTML.
- A block reference is data too: only its local id, target block, and note. Its card content is derived at render time from the block.
- The renderer accepts JSON only and computes layout, collision avoidance, and interaction.
- Never ask an extraction agent to place or render nodes.

## Rendering rules

Layout is **fully owned** by `scripts/render_flow.py`. Read [references/render-layout.md](references/render-layout.md) for the current contract (rows, columns, islands, post-backs, constants). Summary:

- **Rows:** each node alone, then its direct children on one shared row below (top→bottom).
- **Columns:** siblings get sequential slots left→right; **no** rightmost terminal column; **no** special state column.
- **Y:** overlap avoidance **within the same column only**; different columns may share Y.
- **Islands:** disconnected edge components → separate vertical sections with dashed frames.
- **Post-backs:** edge to earlier **STATE** → `{state}__end` pill; other back edges dropped.
- **No-ops:** pruned before render (verify lines only, no `noop` nodes on canvas).
- **Client:** never re-run `layoutRows()` in `render()` — trust Python x/y.

Visual / interaction:

- Full-space canvas; floating flow drawer (`FlowDrawer` component).
- `APP_*` states = compact pills; actions = cards; `process` = spinner.
- Blocks: collapsed card default; **⊞ expand sections** inlines; drawer *Shared blocks* + `open ↗`.
- Directional edge ports in JS; selected node highlights in/out edges.
- Arrow keys navigate selection: connected peer in that direction, else layout sibling (left/right share a row; up/down share a column), else nearest node by position.
- Flow drawer: roving `tabIndex` on the active flow; **Tab** / **Enter** to focus and activate. When focus is **inside the drawer**, **↑/↓** move the flow list; **←/→** (and ↑/↓ when focus is elsewhere) move graph selection on the canvas.
- Focus pan: **200ms RAF tween** when moving selection with **canvas arrow keys** only; flow load, click, and drawer flow change snap instantly (`durationMs: 0`). Node center targets **¼ viewport height** from the top; `alignEdges()` after animated pans (`deferEdges` during tween).
- Fit button cycles **Fit W → Fit H → 100%**; initial load keeps **100%** zoom and focuses the first node without refitting.


Read [references/extraction-workflow.md](references/extraction-workflow.md) for scan heuristics. Read [references/hack-and-workaround-scan.md](references/hack-and-workaround-scan.md) before writing nodes. Read [references/graph-format.md](references/graph-format.md) for grammar. Read [references/render-layout.md](references/render-layout.md) for renderer layout. Copy the worker prompt from [references/authoring-contract.md](references/authoring-contract.md).
