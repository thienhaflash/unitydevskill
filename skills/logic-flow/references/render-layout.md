# Renderer layout contract

`scripts/render_flow.py` owns **all** coordinates. The extractor emits zero x/y. The HTML viewer **must not** re-layout nodes on the client (`layoutRows` exists for debugging only — never call it from `render()`).

Regenerate after graph or renderer changes:

```bash
python3 <skill dir>/scripts/extract_flow_data.py MyFlow.flow --lint -o MyFlow.json
python3 <skill dir>/scripts/render_flow.py MyFlow.json -o MyFlow.html --title "My Flow"
```

## Pipeline order (`prepare_layout`)

For each flow (collapsed + expanded), block view, and shared block:

1. `resolve_sections` — inline group/block refs when expanded
2. `prune_omitted_nodes` — drop no-op nodes (`noop`, `No state change`, `*_noop`, id `none`)
3. `resolve_postback_edges` — see below
4. `auto_layout` — assign x/y, frames, islands

## Post-back edges

An edge is a **post-back** when its target is declared **earlier** in the flow node list than its source.

| Target | Renderer behavior |
|--------|-------------------|
| **STATE** (`APP_*`, empty brief) | Clone target as `{id}__end` pill (`postbackTerminal`, `postbackOf`); retarget edge to duplicate. Original state pill may be omitted from layout when only the `__end` duplicate is used. |
| Non-state (ACTION / PROCESS / block) | Edge **dropped** from canvas (logic stays on verify lines). |

Authors keep normal forward edges in source; do **not** hand-author `__end` nodes.

## Layout graph (group level)

Nodes collapse into **layout groups**: expanded block members share one column group (`blockRef`).

Forward layout edges ignore **state-to-earlier-state** back edges (`is_layout_back_edge`). Other back edges are still dropped by `resolve_postback_edges` before layout.

### Rows (`build_layout_rows`)

Top-to-bottom tree walk in declaration order:

1. Each unplaced group starts a **single-node row** `[group]`.
2. All **direct forward children** share **one row** immediately below (siblings left→right).
3. Recurse depth-first into each child.

Orphan original state pills are skipped when a `postbackOf` duplicate exists and the state has no incoming edges (except the flow's first group).

### Columns (`row_slot_map`)

Siblings on the same row get **sequential slots** `0, 1, 2, …` left to right.

**Do not** implement these removed rules (they caused overlap and wrong placement):

- ~~Terminal / no-output nodes in a dedicated rightmost column~~
- ~~Postback `__end` pills forced to a sink column on the source row~~
- ~~Skipping the parent's column when placing children~~
- ~~Special state-only column alignment~~

Terminals and `__end` pills use the same slot rules as every other node.

### Vertical spacing

- `ROW_GAP = 180` — minimum gap between nodes in the **same column** only.
- `resolve_row_y` bumps Y only when a new box would overlap an existing box in that column.
- Different columns **may share the same Y** (row alignment).
- Child row Y = parent bottom + `ROW_GAP` (deferred until parent is placed).

### Constants

| Constant | Value | Role |
|----------|-------|------|
| `NODE_WIDTH` | 340 | Action/process card width |
| `COLUMN_GAP` | 180 | Horizontal step between columns |
| `ROW_GAP` | 180 | Same-column vertical gap |
| `STATE_HEIGHT` | 52 | `APP_*` pill height |
| `ISLAND_GAP` | 160 | Vertical gap between island sections |
| `ISLAND_LABEL_PAD` | 44 | Space above island for section label |

Column X: `70 + slot * (NODE_WIDTH + COLUMN_GAP)`.

## Disconnected islands

Before layout, compute **undirected connected components** over all flow edges.

| Components | Behavior |
|------------|----------|
| 1 | Single canvas; no `islands` metadata |
| 2+ | Each component laid out independently; stacked vertically with `ISLAND_GAP`. Dashed **island section** frame + title (first `APP_*` state title in component, else first node title). |

**Authoring:** edges define connectivity. Missing edges between related nodes will split the journey into separate sections — intentional for dead-end branches (`other_resume`), unintentional if resume dispatch edges were dropped as post-backs.

## Node visuals

| Node | Render |
|------|--------|
| `APP_*` STATE, empty brief | Compact pill (`state-pill`), width from title |
| ACTION / PROCESS | 340px card; role + numbered steps |
| `kind: process` | Yellow process spinner |
| Block / group ref | Collapsed card; expand via **⊞ expand sections** or `open ↗` |
| Expanded block members | Vertical stack inside blue/green frame |

No-op nodes are **pruned** — they never appear (not even as ⊗). Put guard outcomes on `verify` lines.

## Interaction (HTML template)

- Python coordinates are authoritative — hard-refresh after regen (`Cmd+Shift+R`).
- Pan/zoom; **✎ move mode** — drag one or many nodes (Shift/Cmd/Ctrl+click to multi-select; Escape or click empty canvas to clear).
- **💾 Save layout** — persists `{ col, row }` grid index per node (not pixels). Columns use `520px` steps and rows use `180px` steps from origin `70`, matching Python `auto_layout`. Legacy pixel saves still load once.
- **⌗ Snap** — reads live DOM positions, snaps only top-level nodes and root frames to the same `520×180` layout grid, persists into expanded/collapsed source, and skips reloading stale saved layout on the immediate rerender.
- Edge routing in JS (`alignEdges`) only — positions come from Python unless saved layout overrides.
- **Port contract:** every node renders `data-in-ports="top,left"` and `data-out-ports="bottom,right"`. `alignEdges()` reads these attributes via `nodePortSides()` — it never considers other sides. Override per node later by changing the dataset (must stay within the allowed side sets).
- **Frame resize contract:** `resizeOneFrame()` anchors each group/block frame at its stored top-left (`frame.x`, `frame.y`). Content changes grow or shrink **width/height only** (right + bottom edges). The origin never moves; child world positions are preserved by updating local offsets only.
- **Section expand/collapse reflow:** toggling a section captures bounds before/after. **Expand** pushes external nodes/frames at or beyond the old right edge by `Δwidth`, at or beyond the old bottom by `Δheight` (both when bottom-right). **Collapse** pulls nodes below the old bottom up by `-Δheight`, then nodes at/ beyond the old right left by `-Δwidth`, each move skipped when it would overlap the collapsed section bounds.
- **Section origin pin:** every expand/collapse toggle calls `pinSectionOrigin()` once with the visible section bounds (`collapsed card` or `expanded frame`). That writes the same top-left to `flow.nodes`, `expanded.frames`, and keeps one authoritative origin — no separate expand path or inner-node shifting.
- `fit()` frames all nodes after render.

## Verification checklist

After changing the renderer or a large graph:

1. `extract_flow_data.py --lint` clean
2. Regenerate JSON + HTML
3. Spot-check journeys with branches (e.g. pause/resume) and flows with dead-end islands (e.g. `start`, `reset`)
4. Confirm siblings on one row share Y; different columns may align horizontally
5. Confirm `__end` pills sit in flow order, not a far-right column
6. Confirm disconnected subgraphs show separate dashed sections
