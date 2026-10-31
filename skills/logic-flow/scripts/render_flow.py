#!/usr/bin/env python3
"""Render data-only Logic Flow JSON as a self-contained HTML flow.

The text parser remains available to the extractor, but the renderer itself
only consumes JSON. Layout is intentionally owned by this module.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
from pathlib import Path


def parse_text_value(value: str, line_no: int, field_name: str):
    """Accept a legacy string or a JSON array of strings for readable blocks."""
    if not value.startswith("["):
        return value
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"line {line_no}: {field_name} array must be valid JSON") from exc
    if not isinstance(parsed, list) or not parsed or not all(isinstance(item, str) and item.strip() for item in parsed):
        raise ValueError(f"line {line_no}: {field_name} array must contain non-empty strings")
    return parsed


def parse_graph(path: Path) -> dict:
    flows: list[dict] = []
    blocks: list[dict] = []
    stack: list[dict] = []
    blocks_by_id: dict[str, dict] = {}

    def require_frame(line_no: int) -> dict:
        if not stack:
            raise ValueError(f"line {line_no}: statement appears outside a flow, group, or block")
        return stack[-1]

    def endpoint_exists(endpoint: str, line_no: int) -> bool:
        """Flow edges may target a section ref or ref.inner; group edges are local only."""
        frame = stack[-1]
        nodes = frame["nodes"]
        if endpoint in nodes:
            return True
        prefix, _, inner = endpoint.partition(".")
        if not inner:
            ref = nodes.get(prefix)
            return ref is not None and ref.get("kind") in {"block", "group"}
        ref = nodes.get(prefix)
        if not ref or ref.get("kind") not in {"block", "group"}:
            return False
        target_id = ref.get("block") or ref.get("group")
        if ref.get("kind") == "group":
            for group in frame["data"].get("groups", []):
                if group["id"] == target_id:
                    return inner in {node["id"] for node in group["nodes"]}
            return False
        block = blocks_by_id.get(target_id)
        return bool(block and inner in {node["id"] for node in block["nodes"]})

    def add_node(node: dict, line_no: int) -> None:
        frame = stack[-1]
        if node["id"] in frame["ids"]:
            raise ValueError(f"line {line_no}: duplicate node id {node['id']}")
        frame["ids"].add(node["id"])
        frame["data"]["nodes"].append(node)
        frame["nodes"][node["id"]] = node

    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("flow "):
            if stack:
                raise ValueError(f"line {line_no}: previous flow, group, or block is not closed")
            parts = [part.strip() for part in line[5:].split("|", 2)]
            if len(parts) != 3 or not all(parts):
                raise ValueError(f"line {line_no}: flow needs id | title | description")
            stack.append({
                "kind": "flow",
                "data": {"id": parts[0], "title": parts[1], "description": parts[2], "nodes": [], "edges": [], "groups": []},
                "nodes": {},
                "ids": set(),
            })
            continue

        if line.startswith("block "):
            if stack:
                raise ValueError(f"line {line_no}: block must be declared at file scope")
            parts = [part.strip() for part in line[6:].split("|", 2)]
            if len(parts) != 3 or not all(parts):
                raise ValueError(f"line {line_no}: block needs id | title | description")
            stack.append({
                "kind": "block",
                "data": {"id": parts[0], "title": parts[1], "description": parts[2], "nodes": [], "edges": []},
                "nodes": {},
                "ids": set(),
            })
            continue

        if line.startswith("group "):
            frame = require_frame(line_no)
            if frame["kind"] != "flow":
                raise ValueError(f"line {line_no}: group must be declared inside a flow")
            parts = [part.strip() for part in line[6:].split("|", 2)]
            if len(parts) != 3 or not all(parts):
                raise ValueError(f"line {line_no}: group needs id | title | description")
            stack.append({
                "kind": "group",
                "data": {"id": parts[0], "title": parts[1], "description": parts[2], "nodes": [], "edges": []},
                "nodes": {},
                "ids": set(),
            })
            continue

        if line == "endgroup":
            if not stack or stack[-1]["kind"] != "group":
                raise ValueError(f"line {line_no}: endgroup without group")
            group_frame = stack.pop()
            flow_frame = stack[-1]
            group = group_frame["data"]
            if len(group["nodes"]) < 2:
                raise ValueError(f"line {line_no}: group '{group['id']}' needs at least two nodes")
            for node_id in group_frame["ids"]:
                if node_id in flow_frame["ids"]:
                    raise ValueError(f"line {line_no}: group node id '{node_id}' collides with flow scope")
                flow_frame["ids"].add(node_id)
            flow_frame["data"].setdefault("groups", []).append(group)
            continue

        if line == "endblock":
            if not stack or stack[-1]["kind"] != "block":
                raise ValueError(f"line {line_no}: endblock without block")
            block = stack.pop()["data"]
            blocks.append(block)
            blocks_by_id[block["id"]] = block
            continue

        if line == "end":
            if not stack or stack[-1]["kind"] != "flow":
                raise ValueError(f"line {line_no}: end without flow")
            flows.append(stack.pop()["data"])
            continue

        frame = require_frame(line_no)

        if line.startswith("node "):
            parts = [part.strip() for part in line[5:].split("|")]
            if len(parts) not in {6, 7, 8} or not all(parts):
                raise ValueError(f"line {line_no}: node needs id | title | brief | source | certainty | kind")
            node_id, title, brief, source = parts[:4]
            brief = [] if brief == "-" else parse_text_value(brief, line_no, "node brief")
            if len(parts) == 6:
                certainty, kind = parts[4:]
            elif len(parts) == 7:
                certainty = parts[6]
                kind = "checkpoint"
            else:
                _, _, certainty, kind = parts[4:]
            if certainty not in {"verified", "inferred", "runtime"}:
                raise ValueError(f"line {line_no}: invalid certainty {certainty}")
            if kind not in {"checkpoint", "process"}:
                raise ValueError(f"line {line_no}: invalid node kind {kind}")
            add_node({
                "id": node_id, "title": title, "brief": brief, "source": source,
                "certainty": certainty, "kind": kind, "tone": None, "x": None, "y": None,
                "stories": [], "verification": [],
            }, line_no)
            continue

        if line.startswith("tone "):
            parts = [part.strip() for part in line[5:].split("|", 1)]
            if len(parts) != 2 or not all(parts):
                raise ValueError(f"line {line_no}: tone needs node-id | dispatch|callback")
            node_id, tone = parts
            if node_id not in frame["nodes"]:
                raise ValueError(f"line {line_no}: tone references missing node {node_id}")
            if tone not in {"dispatch", "callback"}:
                raise ValueError(f"line {line_no}: tone must be dispatch or callback")
            frame["nodes"][node_id]["tone"] = tone
            continue

        if line.startswith("useblock "):
            if frame["kind"] != "flow":
                raise ValueError(f"line {line_no}: useblock is only valid inside a flow")
            parts = [part.strip() for part in line[9:].split("|")]
            if len(parts) not in {2, 3} or not all(parts[:2]):
                raise ValueError(f"line {line_no}: useblock needs local-id | block-id [| note]")
            node_id, block_id, note = parts[0], parts[1], parts[2] if len(parts) == 3 else ""
            add_node({
                "id": node_id, "title": "", "brief": [], "source": "", "certainty": "verified",
                "kind": "block", "block": block_id, "note": note, "x": None, "y": None,
                "stories": [], "verification": [],
            }, line_no)
            continue

        if line.startswith("usegroup "):
            if frame["kind"] != "flow":
                raise ValueError(f"line {line_no}: usegroup is only valid inside a flow")
            parts = [part.strip() for part in line[9:].split("|")]
            if len(parts) not in {2, 3} or not all(parts[:2]):
                raise ValueError(f"line {line_no}: usegroup needs local-id | group-id [| note]")
            node_id, group_id, note = parts[0], parts[1], parts[2] if len(parts) == 3 else ""
            add_node({
                "id": node_id, "title": "", "brief": [], "source": "", "certainty": "verified",
                "kind": "group", "group": group_id, "note": note, "x": None, "y": None,
                "stories": [], "verification": [],
            }, line_no)
            continue

        if line.startswith("story ") or line.startswith("verify "):
            kind, remainder = line.split(" ", 1)
            parts = [part.strip() for part in remainder.split("|", 1)]
            if len(parts) != 2 or not all(parts) or parts[0] not in frame["nodes"]:
                raise ValueError(f"line {line_no}: {kind} needs an existing node id | text")
            frame["nodes"][parts[0]]["stories" if kind == "story" else "verification"].append(parts[1])
            continue

        if line.startswith("step "):
            parts = [part.strip() for part in line[5:].split("|", 1)]
            if len(parts) != 2 or not all(parts) or parts[0] not in frame["nodes"]:
                raise ValueError(f"line {line_no}: step needs an existing node id | text")
            node = frame["nodes"][parts[0]]
            if not isinstance(node["brief"], list):
                node["brief"] = [node["brief"]] if node["brief"] else []
            node["brief"].append(parts[1])
            continue

        if line.startswith("edge "):
            remainder = line[5:]
            if "|" not in remainder or "->" not in remainder.split("|", 1)[0]:
                raise ValueError(f"line {line_no}: edge needs from -> to | label")
            route, label = [part.strip() for part in remainder.split("|", 1)]
            source_id, target_id = [part.strip() for part in route.split("->", 1)]
            if frame["kind"] == "group":
                if source_id not in frame["nodes"] or target_id not in frame["nodes"] or not label:
                    raise ValueError(f"line {line_no}: edge references missing node or has empty label")
            elif not endpoint_exists(source_id, line_no) or not endpoint_exists(target_id, line_no) or not label:
                raise ValueError(f"line {line_no}: edge references missing node or has empty label")
            frame["data"]["edges"].append({"from": source_id, "to": target_id, "label": label})
            continue

        raise ValueError(f"line {line_no}: unknown statement")

    if stack:
        kind = stack[-1]["kind"]
        closer = "endgroup" if kind == "group" else "endblock" if kind == "block" else "end"
        raise ValueError(f"final {kind} is missing {closer}")
    if not flows:
        raise ValueError("no flows found")

    data: dict = {"flows": flows}
    if blocks:
        data["blocks"] = blocks
    resolve_sections(data)
    return data


SECTION_KINDS = frozenset({"block", "group"})


def section_refs(container: dict) -> list[dict]:
    return [node for node in container["nodes"] if node.get("kind") in SECTION_KINDS]


def section_target(ref: dict) -> str:
    return ref.get("block") or ref.get("group") or ""


def flow_containers(flow: dict, blocks: dict[str, dict]) -> dict[str, dict]:
    containers = dict(blocks)
    for group in flow.get("groups") or []:
        containers[group["id"]] = group
    return containers


def endpoint_exists(endpoint: str, nodes: dict) -> bool:
    """Edges may target a whole section reference or one node inside it (ref.node)."""
    if endpoint in nodes:
        return True
    prefix = endpoint.split(".", 1)[0]
    return "." in endpoint and nodes.get(prefix, {}).get("kind") in SECTION_KINDS


def split_endpoint(endpoint: str, ref_ids: set) -> tuple[str, str]:
    prefix, _, inner = endpoint.partition(".")
    return (prefix, inner) if inner and prefix in ref_ids else (endpoint, "")


def resolve_sections(data: dict) -> None:
    """Validate every useblock/usegroup target and cache collapsed-card previews."""
    blocks = {block["id"]: block for block in data.get("blocks") or []}

    for block in blocks.values():
        for ref in section_refs(block):
            kind = ref.get("kind")
            raise ValueError(
                f"block '{block['id']}' must not contain nested {kind} '{ref['id']}' — keep one sub-graph level"
            )

    for flow in data["flows"]:
        for group in flow.get("groups") or []:
            for ref in section_refs(group):
                kind = ref.get("kind")
                raise ValueError(
                    f"group '{group['id']}' must not contain nested {kind} '{ref['id']}' — keep one sub-graph level"
                )

    for flow in data["flows"]:
        containers = flow_containers(flow, blocks)
        ref_ids = {node["id"] for node in flow["nodes"] if node.get("kind") in SECTION_KINDS}
        inner_ids: dict[str, set[str]] = {}
        for ref in section_refs(flow):
            target_id = section_target(ref)
            target = containers.get(target_id)
            if target is None:
                kind = ref.get("kind")
                raise ValueError(f"{flow['id']}:{ref['id']} uses unknown {kind} '{target_id}'")
            inner = expand_container(target, containers)[0]
            inner_ids[ref["id"]] = {node["id"] for node in inner}
            sources = []
            for node in inner:
                name = str(node.get("source") or "").split("|")[0].strip()
                if name and name not in sources:
                    sources.append(name)
            note = ref.get("note") or ""
            ref.setdefault("stories", [])
            ref.setdefault("verification", [])
            ref["title"] = target["title"]
            ref["brief"] = [note] if note else [target["description"]]
            ref["source"] = ", ".join(sources[:2]) + (" +" if len(sources) > 2 else "")
            ref["sectionId"] = target_id
            ref["sectionCount"] = len(inner)
            ref["preview"] = [node["title"] for node in inner if node["title"]][:5]
            ref["blockId"] = target_id
            ref["blockCount"] = len(inner)

        for edge in flow["edges"]:
            for endpoint in (edge["from"], edge["to"]):
                prefix, inner_id = split_endpoint(endpoint, ref_ids)
                if inner_id and inner_id not in inner_ids.get(prefix, set()):
                    raise ValueError(
                        f"{flow['id']}: edge endpoint '{endpoint}' has no matching node inside the section"
                    )


def expand_container(container: dict, containers: dict) -> tuple[list[dict], list[dict]]:
    """Inline every block reference so a flow can be laid out fully expanded.

    Inner ids are namespaced by the reference id, so the same block can appear
    twice in one flow. Edges into a reference land on the block's entry nodes
    (no inner predecessor) and edges out leave from its exit nodes.
    """
    nodes: list[dict] = []
    edges: list[dict] = [dict(edge) for edge in container["edges"]]
    entries: dict[str, list[str]] = {}
    exits: dict[str, list[str]] = {}

    for node in container["nodes"]:
        if node.get("kind") not in SECTION_KINDS:
            nodes.append(dict(node))
            continue
        target_id = section_target(node)
        target = containers[target_id]
        inner_nodes, inner_edges = expand_container(target, containers)
        prefix = f"{node['id']}__"
        has_incoming = {edge["to"] for edge in inner_edges}
        has_outgoing = {edge["from"] for edge in inner_edges}
        for inner in inner_nodes:
            clone = dict(inner)
            clone["id"] = prefix + inner["id"]
            clone["blockRef"] = node["id"]
            clone["blockOrigin"] = target_id
            clone["blockOriginTitle"] = target["title"]
            clone["sectionScope"] = node["kind"]
            clone["x"] = clone["y"] = None
            nodes.append(clone)
        for edge in inner_edges:
            edges.append({"from": prefix + edge["from"], "to": prefix + edge["to"], "label": edge["label"]})
        entries[node["id"]] = [prefix + n["id"] for n in inner_nodes if n["id"] not in has_incoming] or \
            [prefix + inner_nodes[0]["id"]]
        exits[node["id"]] = [prefix + n["id"] for n in inner_nodes if n["id"] not in has_outgoing] or \
            [prefix + inner_nodes[-1]["id"]]

    ref_ids = set(entries)

    def resolve(endpoint: str, table: dict) -> list[str]:
        prefix, inner = split_endpoint(endpoint, ref_ids)
        if inner:
            return [f"{prefix}__{inner}"]
        return table.get(endpoint, [endpoint])

    rewired: list[dict] = []
    for edge in edges:
        for source_id in resolve(edge["from"], exits):
            for target_id in resolve(edge["to"], entries):
                rewired.append({"from": source_id, "to": target_id, "label": edge["label"]})
    return nodes, rewired


def collapse_container(container: dict) -> tuple[list[dict], list[dict]]:
    """Fold every ref.node edge back onto the block card and drop duplicates."""
    nodes = [dict(node) for node in container["nodes"]]
    ref_ids = {node["id"] for node in nodes if node.get("kind") in SECTION_KINDS}
    edges: list[dict] = []
    seen = set()
    for edge in container["edges"]:
        source_id = split_endpoint(edge["from"], ref_ids)[0]
        target_id = split_endpoint(edge["to"], ref_ids)[0]
        if source_id == target_id and edge["from"] != edge["to"]:
            continue
        key = (source_id, target_id, edge["label"])
        if key in seen:
            continue
        seen.add(key)
        edges.append({"from": source_id, "to": target_id, "label": edge["label"]})
    return nodes, edges


def merge_parallel_edges(edges: list[dict]) -> list[dict]:
    """Combine multiple edges with the same endpoints into one labeled arrow."""
    merged: dict[tuple[str, str], list[str]] = {}
    order: list[tuple[str, str]] = []
    for edge in edges:
        key = (edge["from"], edge["to"])
        label = str(edge.get("label") or "").strip()
        if key not in merged:
            merged[key] = []
            order.append(key)
        if label and label not in merged[key]:
            merged[key].append(label)
    return [
        {"from": source, "to": target, "label": " · ".join(merged[(source, target)])}
        for source, target in order
    ]


def drop_self_loop_edges(edges: list[dict]) -> list[dict]:
    """Self-loops clutter the canvas; keep their meaning on node steps/verify lines."""
    return [edge for edge in edges if edge["from"] != edge["to"]]


def normalize_edges(edges: list[dict]) -> list[dict]:
    return drop_self_loop_edges(merge_parallel_edges(edges))


def is_postback_edge(edge: dict, node_order: dict[str, int]) -> bool:
    """Edge that returns to an earlier-declared node in the same flow view."""
    source = str(edge.get("from") or "")
    target = str(edge.get("to") or "")
    if not source or not target or source == target:
        return False
    return node_order.get(target, 10**9) < node_order.get(source, 10**9)


def resolve_postback_edges(flow: dict) -> None:
    """Route state post-backs to a terminal duplicate; drop other back edges from the canvas."""
    nodes = flow.get("nodes") or []
    edges = flow.get("edges") or []
    if not edges:
        return
    node_order = {node["id"]: index for index, node in enumerate(nodes)}
    nodes_by_id = {node["id"]: node for node in nodes}
    terminal_by_target: dict[str, str] = {}
    rebuilt: list[dict] = []

    for edge in edges:
        if not is_postback_edge(edge, node_order):
            rebuilt.append(edge)
            continue
        target = edge["to"]
        target_node = nodes_by_id.get(target)
        if target_node and is_state_node(target_node):
            if target not in terminal_by_target:
                dup_id = f"{target}__end"
                counter = 2
                while dup_id in nodes_by_id:
                    dup_id = f"{target}__end{counter}"
                    counter += 1
                dup = {**target_node, "id": dup_id, "postbackTerminal": True, "postbackOf": target}
                flow["nodes"].append(dup)
                nodes_by_id[dup_id] = dup
                terminal_by_target[target] = dup_id
            rebuilt.append({**edge, "to": terminal_by_target[target]})
            continue

    flow["edges"] = rebuilt


def should_omit_node(node: dict) -> bool:
    """Nodes excluded from render — early returns belong on verify lines, not nodes."""
    return is_noop_node(node)


def is_noop_node(node: dict) -> bool:
    if node.get("kind") in SECTION_KINDS:
        return False
    title = str(node.get("title") or "").strip().lower()
    node_id = str(node.get("id") or "").strip().lower()
    if node_id == "none":
        return True
    if title == "no state change":
        return True
    if node_id in {"noop", "w7"} or node_id.endswith("_noop"):
        return True
    if " noop" in title or title.endswith("noop"):
        return True
    return False


def prune_omitted_nodes(flow: dict) -> None:
    for group in flow.get("groups") or []:
        prune_omitted_nodes(group)
    omitted = {node["id"] for node in flow["nodes"] if should_omit_node(node)}
    if not omitted:
        return
    flow["nodes"] = [node for node in flow["nodes"] if node["id"] not in omitted]
    flow["edges"] = [
        edge for edge in flow["edges"]
        if edge["from"] not in omitted and edge["to"] not in omitted
    ]


def split_node_body(brief) -> tuple[list[str], list[str]]:
    lines = brief if isinstance(brief, list) else ([brief] if brief else [])
    role: list[str] = []
    steps: list[str] = []
    for line in lines:
        text = str(line).strip()
        if not text or text == "-":
            continue
        if re.match(r"^\d+\.", text):
            steps.append(text)
        else:
            role.append(text)
    return role, steps


NODE_WIDTH = 340
SINK_SIZE = 72
STATE_HEIGHT = 52
COLUMN_GAP = 180
ROW_GAP = 180
INNER_GAP = 64
BLOCK_FRAME_PAD = 18
BLOCK_FRAME_LABEL_PAD = 48
BLOCK_FRAME_EXPAND_PAD = 48
EDGE_PORT_GAP = 6
ISLAND_GAP = 160
ISLAND_LABEL_PAD = 44


def is_sink_node(node: dict) -> bool:
    """Legacy sink styling — same set as omitted no-op nodes (pruned before render)."""
    return is_noop_node(node)


def is_state_node(node: dict) -> bool:
    """Pure game-state checkpoints (APP_*) render as compact pills without source footer."""
    if node.get("kind") in SECTION_KINDS or is_sink_node(node):
        return False
    if node.get("kind") != "checkpoint":
        return False
    title = str(node.get("title") or "").strip()
    if not title.startswith("APP_"):
        return False
    role, steps = split_node_body(node["brief"])
    return not role and not steps


def state_node_width(node: dict) -> int:
    title = str(node.get("title") or "")
    # Uppercase 13px label + 0.05em tracking + 22px side padding; never wrap state titles.
    return max(160, len(title) * 10 + 52)


def node_width(node: dict) -> int:
    if is_sink_node(node):
        return SINK_SIZE
    if is_state_node(node):
        return state_node_width(node)
    return NODE_WIDTH


def estimate_node_height(node: dict) -> int:
    """Estimate rendered height so text/story/verification blocks do not collide."""
    def wrapped_lines(values, width):
        return sum(max(1, math.ceil(len(line) / width)) for value_line in values for line in str(value_line).splitlines() or [""])

    role, steps = split_node_body(node["brief"])
    if node.get("kind") in SECTION_KINDS:
        steps = list(node.get("preview") or [])
    if is_sink_node(node):
        return SINK_SIZE
    if is_state_node(node):
        return STATE_HEIGHT
    role_height = wrapped_lines(role[:3], 46) if role else 0
    step_wrapped = wrapped_lines(steps[:5], 48) if steps else 0
    step_height = step_wrapped * 22 if steps else 0
    divider_height = 18 if role and steps else (14 if role or steps else 0)
    footer_height = 18
    head_extra = 4 if node.get("kind") == "process" else 0
    return (
        50
        + head_extra
        + role_height * 18
        + divider_height
        + step_height
        + footer_height
        + len(node["stories"]) * 40
    )


def block_ref_key(node: dict) -> str | None:
    """Reference id for an expanded block member (e.g. pull__b_begin -> pull)."""
    ref = node.get("blockRef")
    if ref:
        return ref
    node_id = str(node.get("id") or "")
    if "__" in node_id and node.get("blockOrigin"):
        return node_id.split("__", 1)[0]
    return None


def order_group_nodes(group_ids: list[str], nodes: dict, edges: list[dict]) -> list[str]:
    """Topological order for nodes inside one column group."""
    group_set = set(group_ids)
    inner = [edge for edge in edges if edge["from"] in group_set and edge["to"] in group_set]
    indegree = {node_id: 0 for node_id in group_ids}
    outgoing: dict[str, list[str]] = {node_id: [] for node_id in group_ids}
    for edge in inner:
        outgoing[edge["from"]].append(edge["to"])
        indegree[edge["to"]] += 1
    roots = [node_id for node_id, degree in indegree.items() if degree == 0]
    if not roots:
        roots = group_ids[:1]
    order: list[str] = []
    queue = sorted(roots, key=lambda node_id: group_ids.index(node_id))
    seen = set()
    while queue:
        current = queue.pop(0)
        if current in seen:
            continue
        seen.add(current)
        order.append(current)
        for target in outgoing[current]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    for node_id in group_ids:
        if node_id not in seen:
            order.append(node_id)
    return order


def build_column_groups(flow: dict) -> tuple[dict[str, list[str]], dict[str, str]]:
    """Partition nodes into layout groups (expanded block refs collapse to one group)."""
    groups: dict[str, list[str]] = {}
    node_to_group: dict[str, str] = {}
    for node in flow["nodes"]:
        ref = block_ref_key(node)
        group_id = ref or node["id"]
        groups.setdefault(group_id, []).append(node["id"])
        node_to_group[node["id"]] = group_id
    return groups, node_to_group


def group_flow_index(flow: dict, groups: dict[str, list[str]]) -> dict[str, int]:
    """Earliest declaration index for each layout group."""
    order = {node["id"]: index for index, node in enumerate(flow["nodes"])}
    return {group_id: min(order.get(node_id, 10**9) for node_id in member_ids) for group_id, member_ids in groups.items()}


def is_layout_back_edge(
    source: str,
    target: str,
    group_index: dict[str, int],
    nodes: dict,
    groups: dict[str, list[str]],
) -> bool:
    """Ignore only state-to-earlier-state loops; keep branches to earlier-declared actions."""
    if group_index.get(target, 0) > group_index.get(source, 0):
        return False
    target_rep = nodes[groups[target][0]]
    if not is_state_node(target_rep):
        return False
    source_rep = nodes[groups[source][0]]
    return is_state_node(source_rep)


def branch_parent_group(
    branch_row: list[str],
    parents_of: dict[str, set[str]],
) -> str | None:
    for parent in parents_of.get(branch_row[0], ()):
        if all(parent in parents_of.get(child, ()) for child in branch_row):
            return parent
    return None


def branch_primary_group(branch_row: list[str], outgoing: dict[str, list[str]]) -> str:
    return max(branch_row, key=lambda group_id: len(outgoing.get(group_id, [])))


def find_node_islands(flow: dict) -> list[set[str]]:
    """Undirected connected components over flow edges."""
    node_ids = {node["id"] for node in flow["nodes"]}
    adjacency = {node_id: set() for node_id in node_ids}
    for edge in flow["edges"]:
        source, target = edge["from"], edge["to"]
        if source in adjacency and target in adjacency:
            adjacency[source].add(target)
            adjacency[target].add(source)

    order = {node["id"]: index for index, node in enumerate(flow["nodes"])}
    visited: set[str] = set()
    islands: list[set[str]] = []
    for node_id in sorted(node_ids, key=lambda item: order.get(item, 10**9)):
        if node_id in visited:
            continue
        component: set[str] = set()
        stack = [node_id]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            component.add(current)
            stack.extend(adjacency[current] - visited)
        islands.append(component)
    islands.sort(key=lambda comp: min(order.get(node_id, 10**9) for node_id in comp))
    return islands


def island_title(island_nodes: set[str], flow: dict, nodes: dict) -> str:
    for node in flow["nodes"]:
        if node["id"] not in island_nodes:
            continue
        if is_state_node(node):
            return str(node.get("title") or node["id"])
    for node in flow["nodes"]:
        if node["id"] in island_nodes:
            return str(node.get("title") or node["id"])
    return "Isolated section"


def groups_for_island(
    groups: dict[str, list[str]],
    nodes: dict,
    island_nodes: set[str],
) -> set[str]:
    return {
        group_id
        for group_id, member_ids in groups.items()
        if any(nodes[member_id]["id"] in island_nodes for member_id in member_ids)
    }


def island_horizontal_bounds(nodes: dict, island_nodes: set[str]) -> tuple[int, int]:
    xs: list[int] = []
    for node_id in island_nodes:
        node = nodes[node_id]
        if node.get("x") is None:
            continue
        width = int(node.get("w") or NODE_WIDTH)
        xs.append(int(node["x"]))
        xs.append(int(node["x"]) + width)
    if not xs:
        return 40, 1200
    return min(xs), max(xs)


def island_bottom_y(
    groups: dict[str, list[str]],
    group_ids: set[str],
    nodes: dict,
) -> int:
    bottom = 70
    for group_id in group_ids:
        for member_id in groups[group_id]:
            node = nodes[member_id]
            if node.get("y") is None:
                continue
            bottom = max(bottom, int(node["y"]) + estimate_node_height(node))
    return bottom


def build_layout_rows(
    flow: dict,
    nodes: dict,
    edges: list[dict],
    groups: dict[str, list[str]],
    group_index: dict[str, int],
    node_to_group: dict[str, str],
    outgoing: dict[str, list[str]],
) -> list[list[str]]:
    """Rows: each group alone, then its direct children on one shared row below."""
    group_order = sorted(groups.keys(), key=lambda group_id: group_index.get(group_id, 10**9))
    placed: set[str] = set()
    rows: list[list[str]] = []

    def emit_children_rows(parent: str) -> None:
        children = sorted(
            [child for child in outgoing.get(parent, []) if child not in placed],
            key=lambda child: group_index.get(child, 10**9),
        )
        if not children:
            return
        rows.append(children)
        placed.update(children)
        for child in children:
            emit_children_rows(child)

    incoming = {group_id: False for group_id in groups}
    for edge in edges:
        target = node_to_group.get(edge["to"])
        if target:
            incoming[target] = True
    first_group = min(groups.keys(), key=lambda group_id: group_index.get(group_id, 10**9))

    def skip_orphan_state_pill(group_id: str) -> bool:
        if incoming.get(group_id):
            return False
        member_id = groups[group_id][0]
        has_end_dup = any(node.get("postbackOf") == member_id for node in nodes.values())
        return has_end_dup and group_id != first_group

    for group_id in group_order:
        if group_id in placed:
            continue
        rep = nodes[groups[group_id][0]]
        if is_state_node(rep) and skip_orphan_state_pill(group_id):
            placed.add(group_id)
            emit_children_rows(group_id)
            continue
        rows.append([group_id])
        placed.add(group_id)
        emit_children_rows(group_id)
    return rows


def row_slot_map(row: list[str]) -> dict[str, int]:
    """Adjacent columns in flow order."""
    return {group_id: index for index, group_id in enumerate(row)}


def _layout_component(
    flow: dict,
    nodes: dict,
    edges: list[dict],
    groups: dict[str, list[str]],
    node_to_group: dict[str, str],
    group_filter: set[str] | None,
    y_base: int,
) -> list[dict]:
    """Lay out one connected island (or the whole flow when group_filter is None)."""
    active_groups = groups if group_filter is None else {
        group_id: member_ids for group_id, member_ids in groups.items() if group_id in group_filter
    }
    group_index = group_flow_index(flow, active_groups)

    outgoing: dict[str, list[str]] = {group_id: [] for group_id in active_groups}
    parents_of: dict[str, set[str]] = {group_id: set() for group_id in active_groups}
    for edge in edges:
        source = node_to_group.get(edge["from"])
        target = node_to_group.get(edge["to"])
        if not source or not target or source == target:
            continue
        if source not in active_groups or target not in active_groups:
            continue
        if is_layout_back_edge(source, target, group_index, nodes, groups):
            continue
        outgoing[source].append(target)
        parents_of[target].add(source)

    layout_rows = build_layout_rows(
        flow, nodes, edges, active_groups, group_index, node_to_group, outgoing
    )

    frames: list[dict] = []
    left_x = 70
    column_step = NODE_WIDTH + COLUMN_GAP
    start_y = y_base
    column_ranges: dict[int, list[tuple[int, int]]] = {}
    placed_groups: set[str] = set()
    group_slot: dict[str, int] = {}

    def note_column(slot: int, top_y: int, height: int) -> None:
        column_ranges.setdefault(slot, []).append((top_y, top_y + height))

    def resolve_row_y(slots: list[int], desired_y: int, height: int) -> int:
        y = desired_y
        while True:
            bumped = False
            for slot in slots:
                for existing_top, existing_bottom in column_ranges.get(slot, []):
                    if y < existing_bottom + ROW_GAP and y + height + ROW_GAP > existing_top:
                        candidate = existing_bottom + ROW_GAP
                        if candidate > y:
                            y = candidate
                            bumped = True
            if not bumped:
                return y

    def group_top_y(group_id: str) -> int | None:
        member = nodes[active_groups[group_id][0]]
        y = member.get("y")
        return int(y) if y is not None else None

    def already_placed(group_id: str) -> bool:
        return group_id in placed_groups or group_top_y(group_id) is not None

    def row_below_parent(parent: str | None) -> int:
        if not parent:
            return start_y
        parent_y = group_top_y(parent)
        if parent_y is None:
            return start_y
        return parent_y + group_layout_height(parent) + ROW_GAP

    def place_group(group_id: str, group_x: int, group_y: int) -> int:
        member_ids = order_group_nodes(active_groups[group_id], nodes, edges)
        group_top = group_y
        framed = len(member_ids) > 1 and block_ref_key(nodes[member_ids[0]])
        if framed:
            group_y += BLOCK_FRAME_LABEL_PAD
        for member_id in member_ids:
            node = nodes[member_id]
            width = node_width(node)
            node["w"] = width
            node["sink"] = is_sink_node(node)
            node["state"] = is_state_node(node)
            node["x"] = group_x + (NODE_WIDTH - width) // 2
            node["y"] = group_y
            height = estimate_node_height(node)
            group_y += height + (INNER_GAP if member_id != member_ids[-1] else 0)

        if framed:
            first = nodes[member_ids[0]]
            last = nodes[member_ids[-1]]
            frame_height = (last["y"] + estimate_node_height(last) + BLOCK_FRAME_PAD) - (group_top - BLOCK_FRAME_PAD)
            frames.append({
                "id": group_id,
                "title": first.get("blockOriginTitle") or first.get("title") or group_id,
                "scope": first.get("sectionScope") or "block",
                "x": group_x - BLOCK_FRAME_PAD,
                "y": group_top - BLOCK_FRAME_PAD,
                "width": NODE_WIDTH + BLOCK_FRAME_PAD * 2,
                "height": frame_height,
            })
        return max(group_y - group_top, 130)

    def group_layout_height(group_id: str) -> int:
        member_ids = active_groups[group_id]
        heights = [estimate_node_height(nodes[member_id]) for member_id in member_ids]
        if len(member_ids) > 1:
            label_pad = BLOCK_FRAME_LABEL_PAD if block_ref_key(nodes[member_ids[0]]) else 0
            return sum(heights) + INNER_GAP * (len(member_ids) - 1) + label_pad
        return heights[0] if heights else 130

    def place_at(group_id: str, slot: int, group_y: int) -> int:
        if already_placed(group_id):
            return group_layout_height(group_id)
        group_x = left_x + slot * column_step
        row_height = place_group(group_id, group_x, group_y)
        note_column(slot, group_y, row_height)
        placed_groups.add(group_id)
        group_slot[group_id] = slot
        return row_height

    def place_row(row: list[str], parent: str | None) -> None:
        pending = [group_id for group_id in row if not already_placed(group_id)]
        if not pending:
            return
        slots = row_slot_map(row)
        if len(row) == 1 and parent and parent in group_slot:
            slots = {row[0]: group_slot[parent]}
        desired = row_below_parent(parent)
        row_height = max(group_layout_height(group_id) for group_id in pending)
        row_y = resolve_row_y([slots[group_id] for group_id in pending], desired, row_height)
        for group_id in row:
            if already_placed(group_id):
                continue
            place_at(group_id, slots[group_id], row_y)

    def row_parent(row: list[str]) -> str | None:
        if len(row) >= 2:
            return branch_parent_group(row, parents_of)
        parents = sorted(parents_of.get(row[0], ()), key=lambda item: group_index.get(item, 10**9))
        return parents[0] if parents else None

    pending_rows = list(layout_rows)
    while pending_rows:
        deferred: list[list[str]] = []
        for row in pending_rows:
            parent = row_parent(row)
            if parent and not already_placed(parent):
                deferred.append(row)
                continue
            place_row(row, parent)
        if len(deferred) == len(pending_rows):
            for row in deferred:
                place_row(row, row_parent(row))
            break
        pending_rows = deferred

    for frame in frames:
        frame.pop("parent", None)

    return frames


def collect_frame_descendants(frame_id: str, frames: list[dict]) -> set[str]:
    children_by_parent: dict[str, list[str]] = {}
    for frame in frames:
        parent = frame.get("parent")
        if parent:
            children_by_parent.setdefault(parent, []).append(frame["id"])
    out = {frame_id}
    stack = [frame_id]
    while stack:
        current = stack.pop()
        for child in children_by_parent.get(current, []):
            if child not in out:
                out.add(child)
                stack.append(child)
    return out


def shift_frame_subtree(frame_id: str, dx: int, dy: int, frames: list[dict], nodes: list[dict]) -> None:
    if not dx and not dy:
        return
    descendants = collect_frame_descendants(frame_id, frames)
    frame_by_id = {frame["id"]: frame for frame in frames}
    for fid in descendants:
        frame = frame_by_id[fid]
        frame["x"] = int(frame["x"]) + dx
        frame["y"] = int(frame["y"]) + dy
    for node in nodes:
        if node.get("blockRef") in descendants:
            node["x"] = int(node["x"]) + dx
            node["y"] = int(node["y"]) + dy


def frame_content_boxes(frame_id: str, frames: list[dict], nodes: list[dict]) -> list[tuple[int, int, int, int]]:
    boxes: list[tuple[int, int, int, int]] = []
    for node in nodes:
        if node.get("blockRef") != frame_id:
            continue
        width = node_width(node)
        height = estimate_node_height(node)
        x = int(node["x"])
        y = int(node["y"])
        boxes.append((x, y, x + width, y + height))
    for frame in frames:
        if frame.get("parent") == frame_id:
            boxes.append((
                int(frame["x"]),
                int(frame["y"]),
                int(frame["x"]) + int(frame["width"]),
                int(frame["y"]) + int(frame["height"]),
            ))
    return boxes


def recompute_frame_bounds(frame_id: str, frames: list[dict], nodes: list[dict]) -> None:
    frame = next(item for item in frames if item["id"] == frame_id)
    boxes = frame_content_boxes(frame_id, frames, nodes)
    if not boxes:
        return
    min_x = min(box[0] for box in boxes)
    min_y = min(box[1] for box in boxes)
    max_x = max(box[2] for box in boxes)
    max_y = max(box[3] for box in boxes)
    frame["x"] = min_x - BLOCK_FRAME_PAD
    frame["y"] = min_y - BLOCK_FRAME_PAD - BLOCK_FRAME_LABEL_PAD
    frame["width"] = max(NODE_WIDTH + BLOCK_FRAME_PAD * 2, max_x - min_x + BLOCK_FRAME_PAD * 2)
    frame["height"] = max_y - frame["y"] + BLOCK_FRAME_PAD + BLOCK_FRAME_EXPAND_PAD


def nest_block_frames(frames: list[dict], nodes: list[dict]) -> None:
    if not frames:
        return
    frame_by_id = {frame["id"]: frame for frame in frames}
    children_by_parent: dict[str, list[str]] = {}
    for frame in frames:
        parent = frame.get("parent")
        if parent and parent in frame_by_id:
            children_by_parent.setdefault(parent, []).append(frame["id"])

    def frame_depth(frame_id: str) -> int:
        parent = frame_by_id[frame_id].get("parent")
        if not parent or parent not in frame_by_id:
            return 0
        return 1 + frame_depth(parent)

    for frame_id in sorted(frame_by_id.keys(), key=frame_depth):
        child_ids = sorted(
            children_by_parent.get(frame_id, []),
            key=lambda child_id: (int(frame_by_id[child_id]["y"]), int(frame_by_id[child_id]["x"])),
        )
        cursor_y: int | None = None
        for node in nodes:
            if node.get("blockRef") != frame_id:
                continue
            bottom = int(node["y"]) + estimate_node_height(node)
            cursor_y = bottom if cursor_y is None else max(cursor_y, bottom)
        for child_id in child_ids:
            if cursor_y is None:
                parent = frame_by_id[frame_id]
                cursor_y = int(parent["y"]) + BLOCK_FRAME_LABEL_PAD + BLOCK_FRAME_PAD
            target_y = cursor_y + INNER_GAP
            child = frame_by_id[child_id]
            target_x = int(frame_by_id[frame_id]["x"]) + BLOCK_FRAME_PAD
            dx = target_x - int(child["x"])
            dy = target_y - int(child["y"])
            if dx or dy:
                shift_frame_subtree(child_id, dx, dy, frames, nodes)
            recompute_frame_bounds(child_id, frames, nodes)
            cursor_y = int(child["y"]) + int(child["height"]) - BLOCK_FRAME_PAD
        recompute_frame_bounds(frame_id, frames, nodes)


def auto_layout(flow: dict) -> None:
    """Place nodes per column; stack disconnected islands in separate vertical sections."""
    nodes = {node["id"]: node for node in flow["nodes"]}
    edges = flow["edges"]
    groups, node_to_group = build_column_groups(flow)

    islands = find_node_islands(flow)
    all_frames: list[dict] = []

    if len(islands) <= 1:
        all_frames.extend(_layout_component(flow, nodes, edges, groups, node_to_group, None, 70))
        flow.pop("islands", None)
    else:
        flow["islands"] = []
        y_cursor = 70
        for index, island_nodes in enumerate(islands):
            island_groups = groups_for_island(groups, nodes, island_nodes)
            section_top = y_cursor - ISLAND_LABEL_PAD
            island_frames = _layout_component(
                flow, nodes, edges, groups, node_to_group, island_groups, y_cursor
            )
            for node in flow["nodes"]:
                if node["id"] in island_nodes:
                    node["island"] = index
            for frame in island_frames:
                frame["island"] = index
            all_frames.extend(island_frames)
            left_x, right_x = island_horizontal_bounds(nodes, island_nodes)
            bottom_y = island_bottom_y(groups, island_groups, nodes)
            flow["islands"].append({
                "id": f"{flow['id']}-island-{index + 1}",
                "title": island_title(island_nodes, flow, nodes),
                "x": left_x - 24,
                "y": section_top,
                "width": max(right_x - left_x + 48, 800),
                "height": bottom_y - y_cursor + ISLAND_LABEL_PAD,
            })
            y_cursor = bottom_y + ISLAND_GAP

    placed_group_ids = {
        group_id
        for group_id in groups
        if nodes[groups[group_id][0]].get("y") is not None
    }
    omitted_state_ids = {
        nodes[groups[group_id][0]]["id"]
        for group_id in groups
        if group_id not in placed_group_ids
        and is_state_node(nodes[groups[group_id][0]])
        and any(node.get("postbackOf") == nodes[groups[group_id][0]]["id"] for node in nodes.values())
    }
    if omitted_state_ids:
        flow["nodes"] = [node for node in flow["nodes"] if node["id"] not in omitted_state_ids]
        flow["edges"] = [
            edge
            for edge in flow["edges"]
            if edge["from"] not in omitted_state_ids and edge["to"] not in omitted_state_ids
        ]

    flow["frames"] = all_frames


def prepare_layout(data: dict) -> None:
    """Lay out collapsed + expanded views for each flow, and standalone shared blocks."""
    resolve_sections(data)
    blocks = {block["id"]: block for block in data.get("blocks") or []}
    for flow in data["flows"]:
        if section_refs(flow):
            containers = flow_containers(flow, blocks)
            nodes, edges = expand_container(flow, containers)
            edges = normalize_edges(edges)
            expanded = {"id": flow["id"], "nodes": nodes, "edges": edges}
            prune_omitted_nodes(expanded)
            resolve_postback_edges(expanded)
            auto_layout(expanded)
            flow["expanded"] = {
                "nodes": expanded["nodes"],
                "edges": expanded["edges"],
                "frames": expanded.get("frames") or [],
                "islands": expanded.get("islands") or [],
            }
        flow["nodes"], flow["edges"] = collapse_container(flow)
        flow["edges"] = normalize_edges(flow["edges"])
        prune_omitted_nodes(flow)
        resolve_postback_edges(flow)
        auto_layout(flow)
    for block in data.get("blocks") or []:
        nodes, edges = expand_container(block, blocks)
        edges = normalize_edges(edges)
        view = {"id": block["id"], "nodes": nodes, "edges": edges}
        prune_omitted_nodes(view)
        resolve_postback_edges(view)
        for node in view["nodes"]:
            node.setdefault("blockRef", block["id"])
            node.setdefault("blockOrigin", block["id"])
            node.setdefault("blockOriginTitle", block["title"])
        auto_layout(view)
        block["view"] = {
            "nodes": view["nodes"],
            "edges": view["edges"],
            "frames": view.get("frames") or [],
            "islands": view.get("islands") or [],
        }


def render(data: dict, title: str) -> str:
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    safe_title = html.escape(title)
    drawer_component = (Path(__file__).parent.parent / "templates" / "flow-drawer.js").read_text(encoding="utf-8")
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{safe_title}</title>
<style>
:root{{--bg:#0b0f18;--panel:#101827;--panel2:#1b2a43;--line:#304563;--text:#edf3ff;--muted:#95a8c4;--blue:#8eb8ff;--green:#79d8a6;--yellow:#f4c978}}
*{{box-sizing:border-box}}html,body{{width:100%;height:100%;margin:0;overflow:hidden;background:var(--bg);color:var(--text);font:14px/1.45 Inter,system-ui,sans-serif}}
button{{font:inherit;color:inherit;cursor:pointer}}#app{{height:100%;display:flex}}#drawer{{position:fixed;z-index:5;left:20px;top:20px;width:270px;max-height:calc(100vh - 40px);padding:12px;background:rgba(14,21,34,.93);border:1px solid var(--line);border-radius:16px;box-shadow:0 18px 44px #0008;backdrop-filter:blur(12px);overflow:hidden}}
#drawer.collapsed{{width:58px;padding:10px 8px}}#drawer.collapsed .drawer-toggle{{left:8px;right:auto;width:42px;text-align:center}}#drawer.collapsed .flow-list{{padding-top:38px}}#drawer.collapsed .flow-button{{justify-content:center;padding:9px 0}}#drawer.collapsed .flow-number{{flex:0 0 auto;text-align:center}}#drawer.collapsed .flow-title{{display:none}}#drawer.collapsed .flow-button.active{{background:transparent;border-color:transparent;box-shadow:none}}#drawer.collapsed .flow-button.active::after{{content:"";position:absolute;left:12px;right:12px;bottom:3px;height:2px;background:var(--blue);border-radius:2px}}.flow-tooltip{{position:fixed;z-index:100;padding:6px 9px;background:#1a2537;border:1px solid rgba(122,167,255,.42);border-radius:6px;color:#eef4ff;font-size:12px;line-height:1.2;white-space:nowrap;box-shadow:0 6px 16px rgba(0,0,0,.3);pointer-events:none;opacity:0;transform:translateY(-50%);transition:none;animation:none}}.flow-tooltip.visible{{opacity:1}}
#drawer .drawer-toggle{{position:absolute;right:9px;top:9px;width:24px;height:24px;padding:0;border:0;background:none;color:var(--muted);font-size:18px;line-height:24px}}.flow-list{{display:flex;flex-direction:column;gap:3px;padding-top:30px;overflow:auto;max-height:calc(100vh - 64px)}}.flow-button{{position:relative;display:flex;align-items:center;justify-content:flex-start;gap:6px;width:100%;min-height:40px;padding:10px;border:1px solid transparent;border-radius:9px;background:none;color:var(--muted);text-align:left;line-height:1.2}}.flow-number{{flex:0 0 2.2em;text-align:left;font-variant-numeric:tabular-nums}}.flow-title{{min-width:0}}.flow-button:hover{{background:#8eb8ff14;color:var(--text)}}.flow-button.active{{background:#8eb8ff1f;border-color:#8eb8ffaa;box-shadow:inset 3px 0 var(--blue);color:#fff}}
#viewport{{position:relative;flex:1;width:100%;height:100%;overflow:hidden;touch-action:none;cursor:grab;background-image:linear-gradient(#8eb8ff0b 1px,transparent 1px),linear-gradient(90deg,#8eb8ff0b 1px,transparent 1px);background-size:32px 32px}}#viewport.panning{{cursor:grabbing}}#tools{{position:fixed;z-index:4;right:20px;top:16px;display:flex;gap:8px}}#tools button{{height:38px;padding:0 12px;border:1px solid #8eb8ff55;border-radius:9px;background:#0e1420dd;color:#bdcde5}}#world{{position:absolute;left:0;top:0;transform-origin:top left;user-select:none}}svg{{position:absolute;inset:0;overflow:visible;pointer-events:none}}.edge{{fill:none;stroke:#536987;stroke-width:2.2;stroke-dasharray:7 5;opacity:.78}}.edge.input{{stroke:var(--blue);opacity:.95}}.edge.output{{stroke:var(--green);opacity:.95}}.edge-label{{fill:#8496b0;font-size:12px;text-anchor:middle;dominant-baseline:middle}}.edge-label.input{{fill:#b9d1ff}}.edge-label.output{{fill:#9be5bb}}
.node{{position:absolute;width:340px;min-height:130px;padding:13px;border:1px solid #3a4d69;border-radius:11px;background:#182131f5;cursor:default}}.node.process{{border-color:rgba(244,201,120,.7);background:linear-gradient(135deg,rgba(38,43,49,.98),rgba(24,33,49,.96));box-shadow:0 0 0 1px rgba(244,201,120,.2),0 0 18px rgba(244,201,120,.1)}}.node.tone-dispatch{{border-color:rgba(186,154,255,.82);background:linear-gradient(135deg,rgba(44,34,68,.98),rgba(22,28,48,.96));box-shadow:0 0 0 1px rgba(186,154,255,.28),0 0 20px rgba(140,110,255,.12)}}.node.tone-callback{{border-color:rgba(255,186,108,.8);background:linear-gradient(135deg,rgba(52,36,24,.98),rgba(24,30,44,.96));box-shadow:0 0 0 1px rgba(255,186,108,.26),0 0 20px rgba(255,160,72,.1)}}.node.state-pill.tone-callback{{border-color:rgba(255,186,108,.75);background:radial-gradient(ellipse at 50% 30%,rgba(72,52,32,.98) 0%,rgba(28,34,48,.97) 100%)}}.tone-badge{{flex:0 0 auto;margin-top:1px;padding:2px 7px;border-radius:999px;font-size:10px;letter-spacing:.04em;white-space:nowrap;line-height:1.2}}.tone-badge.dispatch{{border:1px solid rgba(186,154,255,.55);background:rgba(186,154,255,.14);color:#dcc8ff}}.tone-badge.callback{{border:1px solid rgba(255,186,108,.55);background:rgba(255,186,108,.12);color:#ffd9b0}}#tone-legend{{display:flex;gap:8px;align-items:center;margin-left:8px;padding-left:10px;border-left:1px solid rgba(142,184,255,.25);font-size:10px;color:#9eb0c8;user-select:none}}#tone-legend span{{display:inline-flex;align-items:center;gap:4px}}.node.selected{{z-index:4;border-color:#dbe8ff;background:rgba(43,61,91,.99);box-shadow:0 0 0 2px rgba(219,232,255,.72),0 0 0 4px rgba(122,167,255,.2),0 0 26px rgba(122,167,255,.22)}}.node.selected h3{{color:#fff}}.node.moving{{cursor:grabbing}}.node-head{{display:flex;align-items:flex-start;justify-content:space-between;gap:8px;cursor:default;min-width:0}}.node-head h3{{min-width:0;flex:1;margin:0 0 7px;font-size:15px;line-height:1.2;overflow-wrap:anywhere}}.node p{{margin:0;color:#b7c4d8;font-size:12px}}.node-role{{margin:0 0 4px;color:#c5d4ea;font-size:12px;line-height:1.35}}.node-role-line{{display:block}}.node-divider{{height:0;border:0;border-top:1px solid #3a4d69;margin:8px 0}}.node-details{{margin:0;padding-left:16px;color:#b7c4d8;font-size:12px;line-height:1.35}}.node-details li{{margin:3px 0}}.node-brief-line{{display:block}}.node-footer{{display:flex;align-items:center;gap:8px;margin-top:9px}}.node-info{{display:inline-flex;align-items:center;justify-content:center;flex:0 0 auto;width:18px;height:18px;padding:0;border:1px solid #8eb8ffaa;border-radius:50%;background:#1b2a43;color:#dbe8ff;font-size:12px;font-weight:700;line-height:1}}.node-info:hover,.node-info:focus{{background:#8eb8ff33;border-color:#dbe8ff;outline:none}}.node-info-tooltip{{position:fixed;z-index:110;max-width:360px;padding:8px 10px;background:#1a2537;border:1px solid rgba(122,167,255,.42);border-radius:6px;color:#eef4ff;font-size:12px;line-height:1.4;box-shadow:0 6px 16px rgba(0,0,0,.3);pointer-events:none;opacity:0;transition:none}}.node-info-tooltip.visible{{opacity:1}}.node-info-tooltip ul{{margin:0;padding-left:16px}}.node-info-tooltip li{{margin:3px 0}}.node-footer small,.node small{{display:block;margin-top:0;color:#8094b1;font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1}}.node-notes{{margin-top:10px;padding-top:9px;border-top:1px solid #8eb8ff33;color:#cbd8ea;font-size:11px}}.node-notes b{{display:block;margin:5px 0;color:var(--yellow);font-size:10px;text-transform:uppercase;letter-spacing:.08em}}.node-notes div{{margin:4px 0}}.process-mark{{display:inline-block;flex:0 0 auto;width:16px;height:16px;margin-top:1px;border:2px solid #f4c97855;border-top-color:var(--yellow);border-radius:50%;font-size:0;line-height:0;animation:process-spin 2s linear infinite;transform-origin:50% 50%;will-change:transform}}@keyframes process-spin{{to{{transform:rotate(360deg)}}}}.edge.active-edge{{stroke:#9fc1ff;stroke-width:3;stroke-dasharray:9 6;animation:edgeFlow .8s linear infinite;opacity:1}}.edge.active-output{{stroke:#79d8a6;stroke-width:2.8;opacity:.94}}.edge.active-input{{stroke:#8eb8ff;stroke-width:2.8;opacity:.94}}.edge-label{{text-anchor:middle}}.edge-label.active-label{{fill:#dbe8ff;font-weight:700;paint-order:stroke fill;stroke:#18263a;stroke-width:9px;stroke-linejoin:round;stroke-linecap:round}}.edge-label.active-output-label{{fill:#9be5bb}}.edge-label.active-input-label{{fill:#b9d1ff}}@keyframes edgeFlow{{to{{stroke-dashoffset:-30}}}}
.node.block{{border-color:rgba(142,184,255,.7);background:linear-gradient(135deg,rgba(29,45,72,.98),rgba(22,31,47,.96));box-shadow:7px 7px 0 -1px rgba(22,31,47,.98),7px 7px 0 0 rgba(142,184,255,.3),14px 14px 0 -1px rgba(22,31,47,.96),14px 14px 0 0 rgba(142,184,255,.16)}}.node.group{{border-color:rgba(126,214,178,.65);background:linear-gradient(135deg,rgba(24,48,40,.98),rgba(20,33,47,.96));box-shadow:7px 7px 0 -1px rgba(20,33,47,.98),7px 7px 0 0 rgba(126,214,178,.28),14px 14px 0 -1px rgba(20,33,47,.96),14px 14px 0 0 rgba(126,214,178,.14)}}.node.block .node-details li,.node.group .node-details li{{color:#c8d8f2}}.node.from-block{{border-left:3px solid rgba(142,184,255,.6)}}.node.from-group{{border-left:3px solid rgba(126,214,178,.55)}}.block-badge{{flex:0 0 auto;margin-top:1px;padding:2px 7px;border:1px solid rgba(142,184,255,.5);border-radius:999px;background:rgba(142,184,255,.12);color:#bcd4ff;font-size:10px;letter-spacing:.04em;white-space:nowrap}}.group-badge{{flex:0 0 auto;margin-top:1px;padding:2px 7px;border:1px solid rgba(126,214,178,.5);border-radius:999px;background:rgba(126,214,178,.12);color:#b9ebd2;font-size:10px;letter-spacing:.04em;white-space:nowrap}}.block-open{{margin-left:auto;padding:2px 8px;border:1px solid rgba(142,184,255,.55);border-radius:7px;background:rgba(142,184,255,.12);color:#cfe0ff;font-size:11px}}.block-open:hover{{background:rgba(142,184,255,.26)}}.origin-tag{{margin-left:auto;color:#7f96b8;font-size:10px;letter-spacing:.04em;white-space:nowrap}}
.block-list{{display:flex;flex-direction:column;gap:3px;margin-top:8px;padding-top:8px;border-top:1px solid var(--line)}}.block-list-label{{padding:0 10px 4px;color:#7f93b2;font-size:10px;text-transform:uppercase;letter-spacing:.1em}}.block-button{{position:relative;display:flex;align-items:center;gap:6px;width:100%;min-height:36px;padding:8px 10px;border:1px solid transparent;border-radius:9px;background:none;color:var(--muted);text-align:left;line-height:1.2}}.block-button:hover{{background:#8eb8ff14;color:var(--text)}}.block-button.active{{background:#8eb8ff1f;border-color:#8eb8ffaa;box-shadow:inset 3px 0 var(--blue);color:#fff}}.block-mark{{flex:0 0 2.2em;color:var(--blue);font-size:12px}}#drawer.collapsed .block-button{{justify-content:center;padding:8px 0}}#drawer.collapsed .block-mark{{flex:0 0 auto;text-align:center}}#drawer.collapsed .block-title{{display:none}}
.block-frame{{position:absolute;border:2px solid rgba(142,184,255,.55);border-radius:16px;background:rgba(142,184,255,.06);box-shadow:inset 0 0 0 1px rgba(142,184,255,.12);pointer-events:none;z-index:0;overflow:visible}}.block-frame.group-frame{{border-color:rgba(126,214,178,.55);background:rgba(126,214,178,.06);box-shadow:inset 0 0 0 1px rgba(126,214,178,.12)}}.block-frame>.node,.block-frame>.block-frame{{position:absolute;pointer-events:auto}}.block-frame-label{{position:absolute;left:14px;top:-11px;padding:2px 10px;border:1px solid rgba(142,184,255,.55);border-radius:999px;background:#152238;color:#bcd4ff;font-size:11px;letter-spacing:.03em;white-space:nowrap}}.block-frame-label.section-frame-label,.node-head h3.section-toggle,.island-section-label.island-drag-label{{pointer-events:auto;cursor:pointer}}.block-frame-label.section-frame-label:hover,.node-head h3.section-toggle:hover,.island-section-label.island-drag-label:hover{{filter:brightness(1.08)}}#viewport.move-mode .block-frame-label.section-frame-label,#viewport.move-mode .node-head h3.section-toggle,#viewport.move-mode .island-section-label.island-drag-label{{cursor:grab}}.group-frame .block-frame-label{{border-color:rgba(126,214,178,.55);color:#b9ebd2}}
.island-section{{position:absolute;border:1px dashed rgba(142,184,255,.35);border-radius:18px;background:rgba(142,184,255,.04);box-shadow:inset 0 0 0 1px rgba(142,184,255,.08);pointer-events:none;z-index:0}}.island-section-label{{position:absolute;left:16px;top:-12px;padding:3px 12px;border:1px solid rgba(142,184,255,.45);border-radius:999px;background:#121c2e;color:#c8dcff;font-size:11px;font-weight:600;letter-spacing:.04em;white-space:nowrap}}
.node.in-frame{{z-index:1}}
.node.sink-minimal{{width:72px;min-height:72px;padding:0;border-radius:999px;display:flex;align-items:center;justify-content:center;border:2px solid #6f86a8;background:radial-gradient(circle at 50% 42%,#243247 0%,#151d2b 100%);box-shadow:inset 0 0 0 1px #8eb8ff22}}.node.sink-minimal.selected{{border-color:#dbe8ff;box-shadow:0 0 0 2px rgba(219,232,255,.45),inset 0 0 0 1px #8eb8ff55}}.node.sink-minimal h3,.node.sink-minimal .node-footer,.node.sink-minimal .node-role,.node.sink-minimal .node-details,.node.sink-minimal .node-divider{{display:none}}.node.sink-card{{width:340px;min-width:340px;max-width:340px}}.sink-mark{{font-size:24px;line-height:1;color:#95a8c4;user-select:none}}.sink-tooltip{{position:fixed;z-index:120;max-width:280px;padding:8px 10px;background:#1a2537;border:1px solid rgba(122,167,255,.42);border-radius:8px;color:#eef4ff;font-size:12px;line-height:1.35;box-shadow:0 6px 16px rgba(0,0,0,.3);pointer-events:none;opacity:0}}.sink-tooltip.visible{{opacity:1}}
.node.state-pill{{width:auto;min-width:0;min-height:52px;height:52px;padding:0 22px;border-radius:999px;display:flex;align-items:center;justify-content:center;border:2px solid rgba(126,180,255,.58);background:radial-gradient(ellipse at 50% 30%,rgba(48,78,118,.98) 0%,rgba(24,38,58,.97) 100%);box-shadow:inset 0 0 0 1px rgba(126,180,255,.18),0 6px 18px rgba(0,0,0,.22)}}.node.state-pill.selected{{border-color:#e8f4ff;box-shadow:0 0 0 2px rgba(219,232,255,.42),inset 0 0 0 1px rgba(126,180,255,.35),0 8px 22px rgba(122,167,255,.16)}}.node.state-pill .node-head{{display:flex;justify-content:center;align-items:center;width:100%;margin:0}}.node.state-pill h3{{flex:0 0 auto;width:auto;max-width:none;margin:0;font-size:13px;font-weight:700;letter-spacing:.05em;text-align:center;white-space:nowrap;overflow-wrap:normal;word-break:keep-all;color:#d9e9ff}}.node.state-pill .node-footer,.node.state-pill .node-role,.node.state-pill .node-details,.node.state-pill .node-divider,.node.state-pill .process-mark,.node.state-pill .node-info{{display:none}}
#viewport:focus{{outline:none}}#viewport:focus-visible{{outline:2px solid rgba(142,184,255,.45);outline-offset:-2px}}.view-title{{position:absolute;margin:0;padding:0;font-size:22px;font-weight:600;line-height:1.25;letter-spacing:-.02em;color:rgba(127,147,178,.52);pointer-events:none;user-select:none;z-index:0;max-width:min(880px,92vw)}}
</style></head><body><div id="app"><div id="drawer-host"></div><main id="viewport" tabindex="0" aria-label="Flow graph canvas. Use arrow keys to move between nodes."><div id="tools"><button id="back" hidden>‹ back to flow</button><button id="blocks" aria-pressed="false" hidden>⊞ expand sections</button><button id="sinks" aria-pressed="false" title="Expand no-op sink nodes">∅</button><button id="snap" title="Snap to detected columns and rows">⌗</button><button id="resetLayout" title="Reset layout to generated positions">↺</button><button id="saveLayout" title="Save node positions for this view">💾</button><button id="fit">100%</button><button id="move" aria-pressed="true">✎</button><div id="tone-legend" aria-hidden="false"><span><span class="tone-badge dispatch">⬡ dispatch</span></span><span><span class="tone-badge callback">⚡ callback</span></span></div></div><div id="world"></div></main></div>
<script>
{drawer_component}
const DATA={payload};
const world=document.getElementById('world'),viewport=document.getElementById('viewport'),drawer=FlowDrawer.mount(document.getElementById('drawer-host')),fitButton=document.getElementById('fit'),moveButton=document.getElementById('move'),blocksButton=document.getElementById('blocks'),sinksButton=document.getElementById('sinks'),backButton=document.getElementById('back'),snapButton=document.getElementById('snap'),resetLayoutButton=document.getElementById('resetLayout'),saveLayoutButton=document.getElementById('saveLayout');
const zoomStorageKey=`logic-flow.zoom:${{location.pathname}}`;
const sinksStorageKey=`logic-flow.sinks:${{location.pathname}}`;
const layoutStorageKey=`logic-flow.layout:${{location.pathname}}`;
const GRID_ORIGIN=70,GRID_CELL=32,LAYOUT_COLUMN_STEP=520,LAYOUT_ROW_STEP=180;
function snapWorldAxis(value,step){{return GRID_ORIGIN+Math.round((value-GRID_ORIGIN)/step)*step}}
function snapWorldPoint(x,y){{return{{x:snapWorldAxis(x,LAYOUT_COLUMN_STEP),y:snapWorldAxis(y,LAYOUT_ROW_STEP)}}}}
function persistViewToSource(f){{const flowMeta=flow();if(!flowMeta)return;if(flowMeta.expanded){{for(const n of f.nodes){{const src=flowMeta.expanded.nodes.find(x=>x.id===n.id);if(src){{src.x=n.x;src.y=n.y}}if(n.kind==='group'||n.kind==='block'){{const fr=flowMeta.expanded.frames?.find(x=>x.id===n.id);if(fr&&blocksExpanded&&!collapsedSections.has(n.id)){{fr.x=n.x;fr.y=n.y}}}}}}for(const fr of f.frames||[]){{const src=flowMeta.expanded.frames?.find(x=>x.id===fr.id);if(src){{src.x=fr.x;src.y=fr.y;src.width=fr.width;src.height=fr.height}}}}}}for(const n of f.nodes){{const collapsed=flowMeta.nodes.find(x=>x.id===n.id);if(collapsed){{collapsed.x=n.x;collapsed.y=n.y}}}}}}
const FRAME_PAD=18,FRAME_LABEL_PAD=48,ROOT_FRAME_LABEL_LEFT=14,ISLAND_LABEL_LEFT=16;
function clampZoom(value){{const n=Number(value);return Number.isFinite(n)?Math.max(.35,Math.min(1.5,n)):1}}
function readZoom(){{try{{return clampZoom(localStorage.getItem(zoomStorageKey))}}catch{{return 1}}}}
function saveZoom(){{try{{localStorage.setItem(zoomStorageKey,String(scale))}}catch{{}}}}
function readSinksExpanded(){{try{{return localStorage.getItem(sinksStorageKey)==='1'}}catch{{return false}}}}
function saveSinksExpanded(){{try{{localStorage.setItem(sinksStorageKey,sinksExpanded?'1':'0')}}catch{{}}}}
let active=DATA.flows[0].id,selectedIds=new Set(),scale=1,panX=0,panY=0,fitMode='manual',collapsed=false,moving=true,panState=null,nodeState=null,sectionDragState=null,blockView=null,blocksExpanded=true,sinksExpanded=readSinksExpanded(),collapsedSections=new Set(),panAnimationId=null;
const boundarySnapshots=new Map(),layoutSnapshots=new Map();
function snapshotBounds(items){{return(items||[]).map(item=>({{id:item.id,x:item.x,y:item.y,width:item.width,height:item.height}}))}}
function snapshotNodes(items){{return(items||[]).map(item=>({{id:item.id,x:item.x,y:item.y}}))}}
function rememberBoundarySnapshots(){{for(const flow of DATA.flows){{if(flow.expanded){{boundarySnapshots.set(flow.id+':expanded:frames',snapshotBounds(flow.expanded.frames));boundarySnapshots.set(flow.id+':expanded:islands',snapshotBounds(flow.expanded.islands))}}boundarySnapshots.set(flow.id+':frames',snapshotBounds(flow.frames));boundarySnapshots.set(flow.id+':islands',snapshotBounds(flow.islands))}}for(const block of DATA.blocks||[]){{boundarySnapshots.set('block:'+block.id+':frames',snapshotBounds(block.view.frames));boundarySnapshots.set('block:'+block.id+':islands',snapshotBounds(block.view.islands))}}}}
function rememberLayoutSnapshots(){{for(const flow of DATA.flows){{layoutSnapshots.set(flow.id+':nodes',snapshotNodes(flow.nodes));if(flow.expanded)layoutSnapshots.set(flow.id+':expanded:nodes',snapshotNodes(flow.expanded.nodes))}}for(const block of DATA.blocks||[])layoutSnapshots.set('block:'+block.id+':nodes',snapshotNodes(block.view.nodes))}}
function restoreItems(items,snap){{if(!items||!snap)return;for(const item of items){{const orig=snap.find(s=>s.id===item.id);if(orig){{item.x=orig.x;item.y=orig.y;item.width=orig.width;item.height=orig.height}}}}}}
function restoreNodes(items,snap){{if(!items||!snap)return;for(const item of items){{const orig=snap.find(s=>s.id===item.id);if(orig){{item.x=orig.x;item.y=orig.y}}}}}}
function restoreViewBoundaries(f){{if(!f)return;const key=f.key;if(key.startsWith('block:')){{restoreItems(f.frames,boundarySnapshots.get(key+':frames'));restoreItems(f.islands,boundarySnapshots.get(key+':islands'));return}}const base=flow().id,expandedKey=base+':expanded';if(key===expandedKey||key.startsWith(expandedKey+':')){{restoreItems(f.frames,boundarySnapshots.get(base+':expanded:frames'));restoreItems(f.islands,boundarySnapshots.get(base+':expanded:islands'));return}}restoreItems(f.frames,boundarySnapshots.get(base+':frames'));restoreItems(f.islands,boundarySnapshots.get(base+':islands'))}}
function restoreSourceLayout(){{if(blockView){{const block=blockById(blockView);if(!block)return;restoreNodes(block.view.nodes,layoutSnapshots.get('block:'+block.id+':nodes'));restoreItems(block.view.frames,boundarySnapshots.get('block:'+block.id+':frames'));restoreItems(block.view.islands,boundarySnapshots.get('block:'+block.id+':islands'));return}}const meta=flow();if(!meta)return;restoreNodes(meta.nodes,layoutSnapshots.get(meta.id+':nodes'));restoreItems(meta.frames,boundarySnapshots.get(meta.id+':frames'));restoreItems(meta.islands,boundarySnapshots.get(meta.id+':islands'));if(meta.expanded){{restoreNodes(meta.expanded.nodes,layoutSnapshots.get(meta.id+':expanded:nodes'));restoreItems(meta.expanded.frames,boundarySnapshots.get(meta.id+':expanded:frames'));restoreItems(meta.expanded.islands,boundarySnapshots.get(meta.id+':expanded:islands'))}}}}
function clearSavedLayoutForCurrentView(){{const store=readLayoutStore();if(blockView){{delete store['block:'+blockView]}}else{{const meta=flow();if(!meta)return;for(const key of Object.keys(store)){{if(key===meta.id||key.startsWith(meta.id+':'))delete store[key]}}}}saveLayoutStore(store)}}
rememberBoundarySnapshots();rememberLayoutSnapshots();
function scheduleFit(){{requestAnimationFrame(()=>fit())}}
function drawerInset(){{const rect=drawer.getBoundingClientRect();return Math.max(rect.right+12,90)}}
function sectionRefNodes(f){{return(f.nodes||[]).filter(n=>n.kind==='group'||n.kind==='block')}}
function collectDescendantFrameIds(rootId,frames){{const children=buildFrameChildren(frames),out=new Set(),walk=id=>{{for(const child of children.get(id)||[]){{if(out.has(child))continue;out.add(child);walk(child)}}}};walk(rootId);return out}}
let pendingSectionReflow=null;
function readSectionBounds(sectionId){{const frameEl=world.querySelector(`[data-frame="${{sectionId}}"]`);if(frameEl)return worldBox(frameEl);const cardEl=world.querySelector(`[data-node="${{sectionId}}"]`);if(cardEl)return worldBox(cardEl);return null}}
function sectionMemberIds(sectionId,exp){{const frames=exp.frames||[],frameIds=new Set([sectionId,...collectDescendantFrameIds(sectionId,frames)]),nodeIds=new Set([sectionId]);for(const n of exp.nodes||[]){{if(n.blockRef&&frameIds.has(n.blockRef))nodeIds.add(n.id)}}return{{frameIds,nodeIds}}}}
function isFrameInSection(fr,frameIds,frameById){{let cur=fr;while(cur){{if(frameIds.has(cur.id))return true;cur=cur.parent?frameById.get(cur.parent):null}}return false}}
function isExternalRootFrame(fr,frameIds,frameById){{if(isFrameInSection(fr,frameIds,frameById))return false;if(!fr.parent)return true;const parent=frameById.get(fr.parent);return parent?isFrameInSection(parent,frameIds,frameById):true}}
function nodeMetaBounds(n){{const el=world.querySelector(`[data-node="${{n.id}}"]`),box=nodeBox(n),w=box.w||340,h=el?.offsetHeight||(box.h||(isStateNode(n)?52:130)),x=Number(n.x)||0,y=Number(n.y)||0;return{{x,y,w,h,right:x+w,bottom:y+h}}}}
function nodeStoredBounds(n){{const box=nodeBox(n),w=box.w||340,h=box.h||(isStateNode(n)?52:isSinkNode(n)&&!sinksExpanded?72:130),x=Number(n.x)||0,y=Number(n.y)||0;return{{x,y,w,h,right:x+w,bottom:y+h}}}}
function frameMetaBounds(fr){{const x=Number(fr.x)||0,y=Number(fr.y)||0,w=Number(fr.width)||340,h=Number(fr.height)||130;return{{x,y,w,h,right:x+w,bottom:y+h}}}}
function rectsOverlap(a,b){{return a.x<b.right&&a.right>b.x&&a.y<b.bottom&&a.bottom>b.y}}
function shiftFrameTree(fr,dx,dy,exp,frameById){{if(!dx&&!dy)return;fr.x=(Number(fr.x)||0)+dx;fr.y=(Number(fr.y)||0)+dy;const collapsed=flow()?.nodes?.find(n=>n.id===fr.id);if(collapsed){{collapsed.x=(Number(collapsed.x)||0)+dx;collapsed.y=(Number(collapsed.y)||0)+dy}}for(const n of exp.nodes||[]){{if(n.blockRef===fr.id){{n.x=(Number(n.x)||0)+dx;n.y=(Number(n.y)||0)+dy}}}}for(const child of exp.frames||[]){{if(child.parent===fr.id)shiftFrameTree(child,dx,dy,exp,frameById)}}}}
function syncCollapsedSectionPos(nodeId,x,y){{const collapsed=flow()?.nodes?.find(n=>n.id===nodeId);if(collapsed){{collapsed.x=x;collapsed.y=y}}}}
function shiftSectionMembers(sectionId,dx,dy,exp){{if(!exp||Math.abs(dx)<0.5&&Math.abs(dy)<0.5)return;const{{frameIds,nodeIds}}=sectionMemberIds(sectionId,exp);for(const n of exp.nodes||[]){{if(nodeIds.has(n.id)&&n.id!==sectionId){{n.x=(Number(n.x)||0)+dx;n.y=(Number(n.y)||0)+dy}}}}for(const fr of exp.frames||[]){{if(frameIds.has(fr.id)&&fr.id!==sectionId){{fr.x=(Number(fr.x)||0)+dx;fr.y=(Number(fr.y)||0)+dy}}}}}}
function layoutSectionMembers(sectionId,originX,originY,exp){{const flowMeta=flow();if(!flowMeta||!exp)return;const bakedFrame=boundarySnapshots.get(flowMeta.id+':expanded:frames')?.find(fr=>fr.id===sectionId);if(!bakedFrame)return;const bakedNodes=layoutSnapshots.get(flowMeta.id+':expanded:nodes')||[],bakedFrames=boundarySnapshots.get(flowMeta.id+':expanded:frames')||[],dx=originX-(Number(bakedFrame.x)||0),dy=originY-(Number(bakedFrame.y)||0),{{frameIds,nodeIds}}=sectionMemberIds(sectionId,exp);for(const n of exp.nodes||[]){{if(!nodeIds.has(n.id)||n.id===sectionId)continue;const baked=bakedNodes.find(x=>x.id===n.id);if(baked){{n.x=(Number(baked.x)||0)+dx;n.y=(Number(baked.y)||0)+dy}}}}for(const fr of exp.frames||[]){{if(!frameIds.has(fr.id)||fr.id===sectionId)continue;const bakedFr=bakedFrames.find(x=>x.id===fr.id);if(bakedFr){{fr.x=(Number(bakedFr.x)||0)+dx;fr.y=(Number(bakedFr.y)||0)+dy}}}}}}
function pinSectionOrigin(sectionId,originBox){{if(!originBox)return;const flowMeta=flow();if(!flowMeta?.expanded){{syncCollapsedSectionPos(sectionId,originBox.x,originBox.y);return}}const exp=flowMeta.expanded,frame=exp.frames?.find(fr=>fr.id===sectionId);if(!frame){{syncCollapsedSectionPos(sectionId,originBox.x,originBox.y);return}}frame.x=originBox.x;frame.y=originBox.y;syncCollapsedSectionPos(sectionId,originBox.x,originBox.y);layoutSectionMembers(sectionId,originBox.x,originBox.y,exp)}}
function applyExpandedPositionsToDom(exp){{const frameById=frameByIdMap(exp.frames||[]);for(const fr of exp.frames||[]){{const el=world.querySelector(`[data-frame="${{fr.id}}"]`);if(!el)continue;const origin=frameParentWorldOrigin(fr,frameById);el.style.left=(fr.x-origin.x)+'px';el.style.top=(fr.y-origin.y)+'px'}}for(const n of exp.nodes||[]){{const el=world.querySelector(`[data-node="${{n.id}}"]`);if(!el)continue;const origin=n.blockRef?{{x:Number(frameById.get(n.blockRef)?.x)||0,y:Number(frameById.get(n.blockRef)?.y)||0}}:{{x:0,y:0}};el.style.left=(n.x-origin.x)+'px';el.style.top=(n.y-origin.y)+'px'}}}}
function applySectionReflow(sectionId,before,after,expanding){{const f=flow();if(!f?.expanded)return;const exp=f.expanded,oldRight=before.x+before.w,oldBottom=before.y+before.h,deltaW=expanding?Math.max(0,after.x+after.w-oldRight):after.w-before.w,deltaH=expanding?Math.max(0,after.y+after.h-oldBottom):after.h-before.h;if(Math.abs(deltaW)<0.5&&Math.abs(deltaH)<0.5)return;const newBounds={{x:after.x,y:after.y,right:after.x+after.w,bottom:after.y+after.h}},{{frameIds,nodeIds}}=sectionMemberIds(sectionId,exp),frameById=frameByIdMap(exp.frames||[]),movableNodes=(exp.nodes||[]).filter(n=>!nodeIds.has(n.id)&&!n.blockRef),movableRootFrames=(exp.frames||[]).filter(fr=>isExternalRootFrame(fr,frameIds,frameById)),edgeEps=0.5;if(expanding){{for(const n of movableNodes){{const b=nodeStoredBounds(n),dx=b.x>=oldRight-edgeEps?deltaW:0,dy=b.y>=oldBottom-edgeEps?deltaH:0;if(dx||dy){{n.x=(Number(n.x)||0)+dx;n.y=(Number(n.y)||0)+dy;syncCollapsedSectionPos(n.id,n.x,n.y)}}}}for(const fr of movableRootFrames){{const b=frameMetaBounds(fr),dx=b.x>=oldRight-edgeEps?deltaW:0,dy=b.y>=oldBottom-edgeEps?deltaH:0;shiftFrameTree(fr,dx,dy,exp,frameById)}}}}else{{if(deltaH<-edgeEps){{const shiftUp=-deltaH;for(const n of movableNodes){{const b=nodeStoredBounds(n);if(b.y>=oldBottom-edgeEps){{const next={{...b,y:b.y-shiftUp,bottom:b.bottom-shiftUp}};if(!rectsOverlap(next,newBounds)){{n.y=(Number(n.y)||0)-shiftUp;syncCollapsedSectionPos(n.id,n.x,n.y)}}}}}}for(const fr of movableRootFrames){{const b=frameMetaBounds(fr);if(b.y>=oldBottom-edgeEps){{const next={{x:b.x,y:b.y-shiftUp,right:b.right,bottom:b.bottom-shiftUp}};if(!rectsOverlap(next,newBounds))shiftFrameTree(fr,0,-shiftUp,exp,frameById)}}}}}}if(deltaW<-edgeEps){{const shiftLeft=-deltaW;for(const n of movableNodes){{const b=nodeStoredBounds(n);if(b.x>=oldRight-edgeEps){{const next={{...b,x:b.x-shiftLeft,right:b.right-shiftLeft}};if(!rectsOverlap(next,newBounds)){{n.x=(Number(n.x)||0)-shiftLeft;syncCollapsedSectionPos(n.id,n.x,n.y)}}}}}}for(const fr of movableRootFrames){{const b=frameMetaBounds(fr);if(b.x>=oldRight-edgeEps){{const next={{x:b.x-shiftLeft,y:b.y,right:b.right-shiftLeft,bottom:b.bottom}};if(!rectsOverlap(next,newBounds))shiftFrameTree(fr,-shiftLeft,0,exp,frameById)}}}}}}}}applyExpandedPositionsToDom(exp);persistViewToSource({{nodes:exp.nodes,frames:exp.frames||[]}});relayoutBoundaries(true);alignEdges();avoidEdgeLabels()}}
function readSectionStoredBounds(sectionId){{const f=flow();if(!f?.expanded)return null;const collapsed=!blocksExpanded||collapsedSections.has(sectionId);if(collapsed){{const ref=f.nodes.find(n=>n.id===sectionId);if(!ref)return null;return nodeStoredBounds(ref)}}const frame=f.expanded.frames?.find(fr=>fr.id===sectionId);return frame?frameMetaBounds(frame):null}}
function finishSectionReflow(){{if(!pendingSectionReflow)return;pendingSectionReflow=null}}
function resolveCollapsedIds(f,exp){{const refs=sectionRefNodes(f),frames=exp.frames||[],frameById=frameByIdMap(frames),collapsed=new Set();for(const id of collapsedSections){{if(refs.some(r=>r.id===id)||frameById.has(id)){{collapsed.add(id);for(const cid of collectDescendantFrameIds(id,frames))collapsed.add(cid)}}}}return collapsed}}
function nodeCollapsedSection(id,collapsedIds,nodeById,frameById){{const n=nodeById.get(id);if(!n)return null;let ref=n.blockRef;while(ref){{if(collapsedIds.has(ref))return ref;ref=frameById.get(ref)?.parent||null}}return null}}
function nodeInCollapsedScope(n,collapsedIds,frameById){{if(!n.blockRef)return false;let ref=n.blockRef;while(ref){{if(collapsedIds.has(ref))return true;ref=frameById.get(ref)?.parent||null}}return false}}
function frameInCollapsedScope(frame,collapsedIds,frameById){{let cur=frame;while(cur){{if(collapsedIds.has(cur.id))return true;cur=cur.parent?frameById.get(cur.parent):null}}return false}}
function edgeThroughCollapsed(edge,collapsedIds,nodeById,frameById){{const proxy=id=>{{const n=nodeById.get(id);if(!n)return{{id,section:null}};const section=nodeCollapsedSection(id,collapsedIds,nodeById,frameById);if(section)return{{id:section,section}};return{{id,section:null}}}};const from=proxy(edge.from),to=proxy(edge.to);if(from.section&&to.section&&from.section===to.section)return null;return{{from:from.id,to:to.id,label:edge.label||''}}}}
function mergeEdgeList(edges){{const merged=new Map(),order=[];for(const edge of edges){{if(!edge||edge.from===edge.to)continue;const key=edge.from+'\\0'+edge.to;if(!merged.has(key)){{merged.set(key,[]);order.push(key)}}const labels=merged.get(key),label=String(edge.label||'').trim();if(label&&!labels.includes(label))labels.push(label)}}return order.map(key=>{{const split=key.indexOf('\\0');return{{from:key.slice(0,split),to:key.slice(split+1),label:merged.get(key).join(' · ')}}}})}}
function sectionExpandedBounds(sectionId,exp){{const flowMeta=flow(),baked=flowMeta&&boundarySnapshots.get(flowMeta.id+':expanded:frames')?.find(fr=>fr.id===sectionId),frame=exp.frames?.find(fr=>fr.id===sectionId),src=baked||frame;if(!src)return null;const top=Number(src.y)||0,bottom=top+(Number(src.height)||0);return{{top,bottom}}}}
function compactForCollapsedSections(f,exp,nodes,frames,collapsedIds){{if(!collapsedIds.size)return;const frameById=frameByIdMap(exp.frames||[]),refs=sectionRefNodes(f),sorted=[...collapsedIds].filter(id=>refs.some(r=>r.id===id)).sort((a,b)=>{{const ay=sectionExpandedBounds(a,exp)?.top||0,by=sectionExpandedBounds(b,exp)?.top||0;return ay-by}});for(const sectionId of sorted){{const frame=exp.frames?.find(fr=>fr.id===sectionId),saved=f.nodes.find(n=>n.id===sectionId),bounds=sectionExpandedBounds(sectionId,exp);if(!frame||!saved||!bounds)continue;const expandedBottom=bounds.bottom,cardTop=Number(saved?.y??frame?.y)||0,cardBottom=cardTop+nodeStoredBounds(saved).h,reduction=expandedBottom-cardBottom;if(reduction<8)continue;const{{frameIds,nodeIds}}=sectionMemberIds(sectionId,exp);for(const n of nodes){{if(nodeIds.has(n.id))continue;let scope=n.blockRef,inScope=false;while(scope){{if(frameIds.has(scope)){{inScope=true;break}}scope=frameById.get(scope)?.parent||null}}if(inScope)continue;if((Number(n.y)||0)>=expandedBottom-0.5){{n.y=(Number(n.y)||0)-reduction;syncCollapsedSectionPos(n.id,n.x,n.y)}}}}for(const fr of frames){{if(isFrameInSection(fr,frameIds,frameById))continue;if((Number(fr.y)||0)>=expandedBottom-0.5)shiftFrameTree(fr,0,-reduction,exp,frameById)}}}}}}
function buildExpandedView(f){{const exp=f.expanded;if(!exp)return null;const refs=sectionRefNodes(f),frames=exp.frames||[],frameById=frameByIdMap(frames),collapsedIds=resolveCollapsedIds(f,exp);const cacheKey=f.id+':expanded'+[...collapsedIds].sort().map(id=>':'+id).join('');if(expandedViewCache&&expandedViewCache.key===cacheKey)return expandedViewCache;if(!collapsedIds.size){{expandedViewCache={{key:cacheKey,nodes:exp.nodes,edges:exp.edges,frames,islands:exp.islands||[]}};return expandedViewCache}}const nodeById=new Map(exp.nodes.map(n=>[n.id,n]));const nodes=exp.nodes.filter(n=>!nodeInCollapsedScope(n,collapsedIds,frameById));for(const ref of refs){{if(collapsedIds.has(ref.id)){{const frame=frames.find(fr=>fr.id===ref.id),saved=f.nodes.find(n=>n.id===ref.id),card={{...ref}};card.x=Number(saved?.x??frame?.x)||0;card.y=Number(saved?.y??frame?.y)||0;nodes.push(card)}}}}const visibleFrames=frames.filter(fr=>!frameInCollapsedScope(fr,collapsedIds,frameById));compactForCollapsedSections(f,exp,nodes,visibleFrames,collapsedIds);const rawEdges=[];for(const edge of exp.edges){{const mapped=edgeThroughCollapsed(edge,collapsedIds,nodeById,frameById);if(mapped)rawEdges.push(mapped)}}const edges=mergeEdgeList(rawEdges);expandedViewCache={{key:cacheKey,nodes,edges,frames:visibleFrames,islands:exp.islands||[]}};return expandedViewCache}}
function toggleSection(sectionId,clientX,clientY){{const f=flow();if(!f)return;const anchor=Number.isFinite(clientX)&&Number.isFinite(clientY)?captureViewAnchor(clientX,clientY):viewAnchorCenter();const before=readSectionBounds(sectionId)||readSectionStoredBounds(sectionId),wasCollapsed=!blocksExpanded||collapsedSections.has(sectionId);if(before)pinSectionOrigin(sectionId,before);if(!blocksExpanded){{blocksExpanded=true;collapsedSections=new Set(sectionRefNodes(f).map(n=>n.id).filter(id=>id!==sectionId))}}else if(collapsedSections.has(sectionId))collapsedSections.delete(sectionId);else collapsedSections.add(sectionId);if(before)pendingSectionReflow={{sectionId,before,expanding:wasCollapsed}};clearViewCache();skipSavedLayoutOnce=true;appliedLayoutKey=null;clearSelection();render(false,anchor)}}
function frameByIdMap(frames){{return new Map((frames||[]).map(fr=>[fr.id,fr]))}}
function layoutOrigin(parentId,frameById){{if(!parentId)return{{x:0,y:0}};const parent=frameById.get(parentId);return{{x:Number(parent?.x)||0,y:Number(parent?.y)||0}}}}
function nodePosStyle(n,origin){{const ox=origin?.x||0,oy=origin?.y||0;return `left:${{(Number(n.x)||0)-ox}}px;top:${{(Number(n.y)||0)-oy}}px;`}}
function worldBox(el){{let x=0,y=0,cur=el;while(cur&&cur!==world){{x+=cur.offsetLeft;y+=cur.offsetTop;cur=cur.offsetParent}}return{{x,y,w:el.offsetWidth,h:el.offsetHeight,right:x+el.offsetWidth,bottom:y+el.offsetHeight}}}}
function frameDirectChildren(frameEl){{return[...frameEl.children].filter(el=>el.classList.contains('node')||el.classList.contains('block-frame'))}}
function syncWorldCoordsFromDom(){{const f=activeView();for(const frameEl of world.querySelectorAll('.block-frame')){{const meta=(f.frames||[]).find(fr=>fr.id===frameEl.dataset.frame);if(!meta)continue;const box=worldBox(frameEl);meta.x=box.x;meta.y=box.y;meta.width=box.w;meta.height=box.h}}for(const nodeEl of world.querySelectorAll('.node[data-node]')){{const meta=f.nodes.find(n=>n.id===nodeEl.dataset.node);if(!meta)continue;const box=worldBox(nodeEl);meta.x=box.x;meta.y=box.y}}}}
function frameTreeHtml(frame,f,frameById,children,parentFrame){{const parentOrigin=parentFrame?{{x:Number(parentFrame.x)||0,y:Number(parentFrame.y)||0}}:{{x:0,y:0}},frameOrigin={{x:Number(frame.x)||0,y:Number(frame.y)||0}},localX=frameOrigin.x-parentOrigin.x,localY=frameOrigin.y-parentOrigin.y,childIds=children.get(frame.id)||[],members=f.nodes.filter(n=>n.blockRef===frame.id),inner=childIds.map(id=>{{const child=frameById.get(id);return child?frameTreeHtml(child,f,frameById,children,frame):''}}).join('')+members.map(n=>node(n,frameOrigin)).join(''),cls=frame.scope==='group'?'block-frame group-frame':'block-frame';return `<div class="${{cls}}" data-frame="${{escAttr(frame.id)}}" style="left:${{localX}}px;top:${{localY}}px;width:${{frame.width}}px;height:${{frame.height}}px"><span class="block-frame-label section-frame-label" data-section-toggle="${{escAttr(frame.id)}}" style="left:${{ROOT_FRAME_LABEL_LEFT}}px">▾ ${{esc(frame.title)}}</span>${{inner}}</div>`}}
function worldBodyHtml(f){{const frameById=frameByIdMap(f.frames),children=buildFrameChildren(f.frames),rootFrames=(f.frames||[]).filter(fr=>!fr.parent),topNodes=f.nodes.filter(n=>!n.blockRef);return `${{islandHtml(f.islands)}}${{topNodes.map(n=>node(n)).join('')}}${{rootFrames.map(fr=>frameTreeHtml(fr,f,frameById,children,null)).join('')}}`}}
function applySavedLayout(f){{if(appliedLayoutKey===f.key)return;appliedLayoutKey=f.key;const saved=readLayoutStore()[f.key];if(!saved)return;const frameById=frameByIdMap(f.frames);const nodeSaved=saved.nodes||saved;for(const n of f.nodes){{const pos=nodeSaved[n.id];if(!pos)continue;const relative=Object.prototype.hasOwnProperty.call(pos,'parent'),origin=relative?layoutOrigin(pos.parent,frameById):{{x:0,y:0}};if(Number.isFinite(pos.col)&&Number.isFinite(pos.row)){{const p=gridToPos(n,pos.col,pos.row);n.x=origin.x+p.x;n.y=origin.y+p.y}}else if(Number.isFinite(pos.x)&&Number.isFinite(pos.y)){{n.x=origin.x+pos.x;n.y=origin.y+pos.y}}}}}}
function captureLayoutGrid(f){{const frameById=frameByIdMap(f.frames),out={{nodes:{{}}}};for(const n of f.nodes){{const parentId=n.blockRef||null,origin=layoutOrigin(parentId,frameById),g=posToGrid(n,(Number(n.x)||0)-origin.x,(Number(n.y)||0)-origin.y);out.nodes[n.id]={{parent:parentId,col:g.col,row:g.row}}}}return out}}
function sectionDragTargets(sectionId,anchorEl){{const f=activeView(),targets=[],sectionMeta=f.nodes.find(n=>n.id===sectionId&&(n.kind==='group'||n.kind==='block')),collapsed=!!sectionMeta&&(!blocksExpanded||collapsedSections.has(sectionId));if(anchorEl){{const frameEl=anchorEl.closest(`.block-frame[data-frame="${{sectionId}}"]`),frameMeta=(f.frames||[]).find(fr=>fr.id===sectionId);if(frameEl&&frameMeta&&!collapsed){{targets.push({{el:frameEl,n:null,frame:frameMeta,island:null}});return targets}}const nodeEl=anchorEl.closest(`[data-node="${{sectionId}}"]`);if(nodeEl&&sectionMeta&&collapsed){{targets.push({{el:nodeEl,n:sectionMeta,frame:null,island:null}});return targets}}}}if(collapsed){{const n=sectionMeta,el=world.querySelector(`[data-node="${{sectionId}}"]`);if(n&&el)targets.push({{el,n,frame:null,island:null}});return targets}}const frameEl=world.querySelector(`[data-frame="${{sectionId}}"]`),frameMeta=(f.frames||[]).find(fr=>fr.id===sectionId);if(frameEl&&frameMeta){{targets.push({{el:frameEl,n:null,frame:frameMeta,island:null}});return targets}}for(const n of f.nodes){{if(n.blockRef!==sectionId)continue;const el=world.querySelector(`[data-node="${{n.id}}"]`);if(el)targets.push({{el,n,frame:null,island:null}})}}return targets}}
function islandDragTargets(islandId){{const f=activeView(),targets=[],seenNodes=new Set(),seenFrames=new Set(),islandIndex=islandIndexFromId(islandId);if(islandIndex===null)return targets;const islandFrames=(f.frames||[]).filter(fr=>fr.island===islandIndex),islandFrameIds=new Set(islandFrames.map(fr=>fr.id)),draggedFrameIds=new Set();for(const fr of islandFrames){{if(fr.parent&&islandFrameIds.has(fr.parent))continue;draggedFrameIds.add(fr.id);const frameEl=world.querySelector(`[data-frame="${{fr.id}}"]`);if(frameEl&&!seenFrames.has(fr.id)){{seenFrames.add(fr.id);targets.push({{el:frameEl,n:null,frame:fr,island:null}})}}}}const framedNodeIds=new Set(f.nodes.filter(n=>n.blockRef&&draggedFrameIds.has(n.blockRef)).map(n=>n.id));for(const n of f.nodes){{if(n.island===islandIndex&&!seenNodes.has(n.id)&&!framedNodeIds.has(n.id)){{const el=world.querySelector(`[data-node="${{n.id}}"]`);if(el){{seenNodes.add(n.id);targets.push({{el,n,frame:null,island:null}})}}}}}}const islandEl=world.querySelector(`[data-island="${{islandId}}"]`),islandMeta=(f.islands||[]).find(i=>i.id===islandId);if(islandEl&&islandMeta)targets.push({{el:islandEl,n:null,frame:null,island:islandMeta}});return targets}}
function syncDragTargetsToSource(targets){{const f=flow();if(!f&&!blockView)return;const b=blockView?blockById(blockView):null,storeNodes=b?b.view.nodes:(f.expanded&&f.expanded.nodes)||null,storeFrames=b?b.view.frames:(f.expanded&&f.expanded.frames)||null,storeIslands=b?b.view.islands:(f.expanded&&f.expanded.islands)||f.islands||null,seenNodes=new Set(),seenFrames=new Set();for(const item of targets){{if(item.n&&!seenNodes.has(item.n.id)){{seenNodes.add(item.n.id);const source=storeNodes&&storeNodes.find(x=>x.id===item.n.id);if(source){{source.x=item.n.x;source.y=item.n.y}}if(f){{const collapsed=f.nodes.find(x=>x.id===item.n.id);if(collapsed){{collapsed.x=item.n.x;collapsed.y=item.n.y}}if((item.n.kind==='group'||item.n.kind==='block')&&!seenFrames.has(item.n.id)){{seenFrames.add(item.n.id);const sourceFrame=storeFrames&&storeFrames.find(fr=>fr.id===item.n.id);if(sourceFrame){{const prevX=Number(sourceFrame.x)||0,prevY=Number(sourceFrame.y)||0;sourceFrame.x=item.n.x;sourceFrame.y=item.n.y;if(f?.expanded)shiftSectionMembers(item.n.id,item.n.x-prevX,item.n.y-prevY,f.expanded)}}}}}}}}if(item.frame&&!seenFrames.has(item.frame.id)){{seenFrames.add(item.frame.id);const sourceFrame=storeFrames&&storeFrames.find(fr=>fr.id===item.frame.id);if(sourceFrame){{sourceFrame.x=item.frame.x;sourceFrame.y=item.frame.y;sourceFrame.width=item.frame.width;sourceFrame.height=item.frame.height;if(Number.isFinite(item.frame.labelX))sourceFrame.labelX=item.frame.labelX;if(f){{const collapsed=f.nodes.find(x=>x.id===item.frame.id);if(collapsed){{collapsed.x=item.frame.x;collapsed.y=item.frame.y}}}}}}}}if(item.island){{const sourceIsland=storeIslands&&storeIslands.find(i=>i.id===item.island.id);if(sourceIsland){{sourceIsland.x=item.island.x;sourceIsland.y=item.island.y;const w=Number.parseFloat(item.el.style.width),h=Number.parseFloat(item.el.style.height);if(Number.isFinite(w))sourceIsland.width=w;if(Number.isFinite(h))sourceIsland.height=h;if(Number.isFinite(item.island.labelX))sourceIsland.labelX=item.island.labelX}}}}}}}}
function syncSectionPositionsToSource(sectionId){{syncDragTargetsToSource(sectionDragTargets(sectionId))}}
function frameParentWorldOrigin(frame,frameById){{if(!frame||!frame.parent)return{{x:0,y:0}};const parentEl=world.querySelector(`[data-frame="${{frame.parent}}"]`);if(parentEl)return worldBox(parentEl);const parent=frameById.get(frame.parent);return{{x:Number(parent?.x)||0,y:Number(parent?.y)||0}}}}
function syncSectionDragTargetsFromDom(targets){{for(const item of targets){{const box=worldBox(item.el);if(item.n){{item.n.x=box.x;item.n.y=box.y}}else if(item.frame){{item.frame.x=box.x;item.frame.y=box.y}}else if(item.island){{item.island.x=box.x;item.island.y=box.y}}}}}}
function sectionDragSnapshot(targets){{return targets.map(item=>{{const box=worldBox(item.el);return{{item,x:box.x,y:box.y,kind:item.n?'node':item.frame?'frame':'island'}}}})}}
function applySectionDragDelta(snapshots,dx,dy){{const frameById=frameByIdMap(activeView().frames);for(const snap of snapshots){{const nx=snap.x+dx,ny=snap.y+dy;if(snap.kind==='node'){{snap.item.n.x=nx;snap.item.n.y=ny;const frameEl=snap.item.el.closest('.block-frame'),origin=frameEl?worldBox(frameEl):{{x:0,y:0}};snap.item.el.style.left=(nx-origin.x)+'px';snap.item.el.style.top=(ny-origin.y)+'px'}}else if(snap.kind==='frame'){{const frame=snap.item.frame,origin=frameParentWorldOrigin(frame,frameById);frame.x=nx;frame.y=ny;snap.item.el.style.left=(nx-origin.x)+'px';snap.item.el.style.top=(ny-origin.y)+'px'}}else if(snap.kind==='island'){{snap.item.island.x=nx;snap.item.island.y=ny;snap.item.el.style.left=nx+'px';snap.item.el.style.top=ny+'px'}}}}}}
function finishBoundaryDrag(moved,targets,onTap,clientX,clientY,dragKind){{if(moved){{syncWorldCoordsFromDom();syncDragTargetsToSource(targets);relayoutBoundaries();alignEdges();fitMode='manual';return}}if(onTap)onTap(clientX,clientY)}}
function wireBoundaryDrag(el,getTargets,dragKind,onTap){{el.onpointerdown=e=>{{e.stopPropagation();if(moving&&e.button===0){{const targets=getTargets(el);if(!targets.length)return;syncSectionDragTargetsFromDom(targets);sectionDragState={{dragKind,targets,anchorEl:el,moved:false,start:sectionDragSnapshot(targets),x:e.clientX,y:e.clientY,onTap}};el.setPointerCapture(e.pointerId)}}}};el.onpointermove=e=>{{if(!sectionDragState||sectionDragState.anchorEl!==el)return;const dx=(e.clientX-sectionDragState.x)/scale,dy=(e.clientY-sectionDragState.y)/scale;if(Math.abs(dx)+Math.abs(dy)>3)sectionDragState.moved=true;applySectionDragDelta(sectionDragState.start,dx,dy);alignEdges();resizeFrames();resizeIslands()}};el.onpointerup=e=>{{if(sectionDragState?.anchorEl!==el)return;const moved=sectionDragState.moved,targets=sectionDragState.targets,onTapHandler=sectionDragState.onTap,kind=sectionDragState.dragKind;sectionDragState=null;try{{el.releasePointerCapture(e.pointerId)}}catch{{}}finishBoundaryDrag(moved,targets,onTapHandler,e.clientX,e.clientY,kind)}}}}
function wireSectionToggles(){{world.querySelectorAll('[data-section-toggle]').forEach(el=>{{const sectionId=el.dataset.sectionToggle,expanded=blocksExpanded&&!collapsedSections.has(sectionId);el.setAttribute('role','button');el.setAttribute('tabindex','0');el.setAttribute('aria-expanded',String(expanded));el.setAttribute('aria-label',(expanded?'Collapse ':'Expand ')+el.textContent.trim());el.onclick=e=>e.preventDefault();el.onkeydown=e=>{{if(e.key==='Enter'||e.key===' '){{e.preventDefault();toggleSection(sectionId)}}}};wireBoundaryDrag(el,anchorEl=>sectionDragTargets(sectionId,anchorEl),'section',(x,y)=>toggleSection(sectionId,x,y))}});world.querySelectorAll('[data-island-drag]').forEach(el=>{{const islandId=el.dataset.islandDrag;el.setAttribute('role','button');el.setAttribute('tabindex','0');el.setAttribute('aria-label','Drag island '+el.textContent.trim());wireBoundaryDrag(el,()=>islandDragTargets(islandId),'island',null)}})}}
function nodeSelected(id){{return selectedIds.has(id)}}
function clearSelection(){{selectedIds.clear()}}
function syncSelectionVisuals(options){{const deferEdges=!!options?.deferEdges;world.querySelectorAll('.node[data-node]').forEach(el=>{{el.classList.toggle('selected',selectedIds.has(el.dataset.node))}});world.querySelectorAll('.edge[data-from]').forEach(path=>{{const from=path.dataset.from,to=path.dataset.to,outputActive=nodeSelected(from),inputActive=nodeSelected(to),activeEdge=outputActive||inputActive;path.classList.toggle('active-edge',activeEdge);path.classList.toggle('active-output',outputActive);path.classList.toggle('active-input',inputActive);const label=world.querySelector(`[data-label="${{from}}:${{to}}"]`);if(label){{label.classList.toggle('active-label',activeEdge);label.classList.toggle('active-output-label',outputActive);label.classList.toggle('active-input-label',inputActive)}}}});if(!deferEdges)alignEdges()}}
function toggleSelection(id){{if(selectedIds.has(id))selectedIds.delete(id);else selectedIds.add(id)}}
function setSingleSelection(id){{selectedIds=new Set([id])}}
function nodeNavCenter(n){{const box=nodeBox(n),w=box.w||340,h=box.h||(isStateNode(n)?52:isSinkNode(n)&&!sinksExpanded?72:130);return{{x:(Number(n.x)||0)+w/2,y:(Number(n.y)||0)+h/2}}}}
function navKeyDirection(key){{return key==='ArrowLeft'?'left':key==='ArrowRight'?'right':key==='ArrowUp'?'up':key==='ArrowDown'?'down':null}}
function navPrimaryDelta(dir,center,target){{const dx=target.x-center.x,dy=target.y-center.y;if(dir==='right')return dx;if(dir==='left')return-dx;if(dir==='down')return dy;return-dy}}
function navInDirection(center,target,dir,eps=6){{const dx=target.x-center.x,dy=target.y-center.y;if(dir==='right')return dx>eps&&Math.abs(dy)<=Math.abs(dx)+eps;if(dir==='left')return dx<-eps&&Math.abs(dy)<=Math.abs(-dx)+eps;if(dir==='down')return dy>eps&&Math.abs(dx)<=Math.abs(dy)+eps;return dy<-eps&&Math.abs(dx)<=Math.abs(-dy)+eps}}
function navConnectedIds(currentId,dir,f){{const nodesById=new Map(f.nodes.map(n=>[n.id,n])),cur=nodesById.get(currentId);if(!cur)return[];const center=nodeNavCenter(cur),out=dir==='right'||dir==='down',hits=[];for(const edge of f.edges||[]){{const peerId=out?edge.from===currentId?edge.to:null:edge.to===currentId?edge.from:null;if(!peerId||peerId===currentId)continue;const peer=nodesById.get(peerId);if(!peer)continue;const pc=nodeNavCenter(peer);if(!navInDirection(center,pc,dir))continue;hits.push({{id:peerId,dist:Math.hypot(pc.x-center.x,pc.y-center.y)}})}}hits.sort((a,b)=>a.dist-b.dist);return hits.map(h=>h.id)}}
function navSiblingId(currentId,dir,f){{const cur=f.nodes.find(n=>n.id===currentId);if(!cur)return null;const grid=posToGrid(cur,Number(cur.x)||0,Number(cur.y)||0),peers=f.nodes.filter(n=>n.id!==currentId);if(dir==='left'||dir==='right'){{const rowPeers=peers.filter(n=>posToGrid(n,Number(n.x)||0,Number(n.y)||0).row===grid.row);if(!rowPeers.length)return null;const ranked=rowPeers.map(n=>{{const g=posToGrid(n,Number(n.x)||0,Number(n.y)||0);return{{id:n.id,col:g.col,dy:Math.abs((Number(n.y)||0)-(Number(cur.y)||0))}}}}).filter(p=>dir==='left'?p.col<grid.col:p.col>grid.col).sort((a,b)=>dir==='left'?b.col-a.col||a.dy-b.dy:a.col-b.col||a.dy-b.dy);return ranked[0]?.id||null}}const colPeers=peers.filter(n=>posToGrid(n,Number(n.x)||0,Number(n.y)||0).col===grid.col);if(!colPeers.length)return null;const ranked=colPeers.map(n=>{{const g=posToGrid(n,Number(n.x)||0,Number(n.y)||0);return{{id:n.id,row:g.row,dx:Math.abs((Number(n.x)||0)-(Number(cur.x)||0))}}}}).filter(p=>dir==='up'?p.row<grid.row:p.row>grid.row).sort((a,b)=>dir==='up'?b.row-a.row||a.dx-b.dx:a.row-b.row||a.dx-b.dx);return ranked[0]?.id||null}}
function navNearestId(currentId,dir,f){{const cur=f.nodes.find(n=>n.id===currentId);if(!cur)return null;const center=nodeNavCenter(cur),best=null;for(const n of f.nodes){{if(n.id===currentId)continue;const pc=nodeNavCenter(n);if(!navInDirection(center,pc,dir))continue;const dist=Math.hypot(pc.x-center.x,pc.y-center.y);if(!best||dist<best.dist)best={{id:n.id,dist}}}}return best?.id||null}}
function navDefaultNodeId(f){{const pick=f.nodes.find(n=>n.kind!=='block'&&n.kind!=='group');return pick?pick.id:null}}
function selectNodeById(id){{if(!id)return;setSingleSelection(id);syncSelectionVisuals()}}
function focusNodeById(id,options){{if(!id)return;const animate=options?.animate===true;setSingleSelection(id);syncSelectionVisuals({{deferEdges:animate}});scrollNodeIntoView(id,{{animate}});focusFlowViewport()}}
function focusFirstNodeInView(){{const f=activeView();focusNodeById(navDefaultNodeId(f),{{animate:false}})}}
function syncFitButtonLabel(){{if(fitMode==='width')fitButton.textContent='Fit W';else if(fitMode==='height')fitButton.textContent='Fit H';else fitButton.textContent=Math.round(scale*100)+'%'}}
function cycleFitMode(){{cancelPanAnimation();if(fitMode==='width')fitMode='height';else if(fitMode==='height'){{fitMode='manual';scale=1}}else fitMode='width';fit();if(fitMode==='manual')saveZoom()}}
function focusFlowViewport(){{if(!viewport)return;try{{viewport.focus({{preventScroll:true}})}}catch{{viewport.focus()}}}}
function cancelPanAnimation(){{if(panAnimationId){{cancelAnimationFrame(panAnimationId);panAnimationId=null}}world.style.transition=''}}
function panFocusForNode(id){{const el=world.querySelector(`[data-node="${{id}}"]`);if(!el)return null;const box=worldBox(el),cx=box.x+box.w/2,cy=box.y+box.h/2,rect=viewport.getBoundingClientRect(),left=drawerInset(),freeW=Math.max(rect.width-left-24,120),freeH=Math.max(rect.height-48,120),targetX=left+freeW/2,targetY=24+freeH/4;return{{x:targetX-cx*scale,y:targetY-cy*scale}}}}
function easeOutCubic(t){{return 1-Math.pow(1-t,3)}}
function easeInOutCubic(t){{return t<0.5?4*t*t*t:1-Math.pow(-2*t+2,3)/2}}
const FOCUS_PAN_DURATION_MS=200;
function animatePanTo(tx,ty,opts){{cancelPanAnimation();fitMode='manual';world.style.transition='';const fixedMs=opts?.durationMs;const startX=panX,startY=panY,dist=Math.hypot(tx-startX,ty-startY);if(fixedMs!==undefined){{if(!fixedMs||dist<0.5){{panX=tx;panY=ty;applyTransform();alignEdges();return}}const t0=performance.now(),duration=fixedMs,step=now=>{{const u=Math.min(1,(now-t0)/duration),e=easeInOutCubic(u);panX=startX+(tx-startX)*e;panY=startY+(ty-startY)*e;applyTransform();if(u<1)panAnimationId=requestAnimationFrame(step);else{{panAnimationId=null;alignEdges()}}}};panAnimationId=requestAnimationFrame(step);return}}if(window.matchMedia('(prefers-reduced-motion: reduce)').matches){{panX=tx;panY=ty;applyTransform();return}}if(dist<2){{panX=tx;panY=ty;applyTransform();return}}const duration=Math.min(520,Math.max(200,dist*0.42)),t0=performance.now(),step=now=>{{const u=Math.min(1,(now-t0)/duration),e=easeOutCubic(u);panX=startX+(tx-startX)*e;panY=startY+(ty-startY)*e;applyTransform();if(u<1)panAnimationId=requestAnimationFrame(step);else{{panAnimationId=null;alignEdges()}}}};panAnimationId=requestAnimationFrame(step)}}
function scrollNodeIntoView(id,options){{const target=panFocusForNode(id);if(!target)return;const durationMs=options?.animate===true?FOCUS_PAN_DURATION_MS:0;animatePanTo(target.x,target.y,{{durationMs}})}}
function navigateSelection(dir){{const f=activeView();if(!f?.nodes?.length)return;let currentId=[...selectedIds][0];if(!currentId){{currentId=navDefaultNodeId(f);if(!currentId)return;focusNodeById(currentId,{{animate:false}});return}}let next=navConnectedIds(currentId,dir,f)[0];if(!next)next=navSiblingId(currentId,dir,f);if(!next)next=navNearestId(currentId,dir,f);if(!next||next===currentId)return;focusNodeById(next,{{animate:true}})}}
function nodeGridSize(n){{const box=nodeBox(n),w=box.w||340,h=box.h||(isStateNode(n)?52:isSinkNode(n)&&!sinksExpanded?72:130);return{{cellW:LAYOUT_COLUMN_STEP,cellH:LAYOUT_ROW_STEP,w,h}}}}
function posToGrid(n,x,y){{return{{col:Math.round((x-GRID_ORIGIN)/LAYOUT_COLUMN_STEP),row:Math.round((y-GRID_ORIGIN)/LAYOUT_ROW_STEP)}}}}
function gridToPos(n,col,row){{return{{x:GRID_ORIGIN+col*LAYOUT_COLUMN_STEP,y:GRID_ORIGIN+row*LAYOUT_ROW_STEP}}}}
function readLayoutStore(){{try{{return JSON.parse(localStorage.getItem(layoutStorageKey)||'{{}}')}}catch{{return{{}}}}}}
function saveLayoutStore(store){{try{{localStorage.setItem(layoutStorageKey,JSON.stringify(store))}}catch{{}}}}
let appliedLayoutKey=null,skipSavedLayoutOnce=false,renderedView=null,expandedViewCache=null;
function clearViewCache(){{renderedView=null;expandedViewCache=null}}
function activeView(){{return renderedView||view()}}
function saveLayout(){{const f=view();const store=readLayoutStore();store[f.key]=captureLayoutGrid(f);saveLayoutStore(store);saveLayoutButton.textContent='✓';saveLayoutButton.style.borderColor='#79d8a6';setTimeout(()=>{{saveLayoutButton.textContent='💾';saveLayoutButton.style.borderColor=''}},1400)}}
function snapLayoutPositions(f){{const frameById=frameByIdMap(f.frames||[]);let moved=0;for(const fr of f.frames||[]){{if(fr.parent)continue;const p=snapWorldPoint(Number(fr.x)||0,Number(fr.y)||0);if(p.x!==fr.x||p.y!==fr.y){{fr.x=p.x;fr.y=p.y;moved++;syncCollapsedSectionPos(fr.id,p.x,p.y)}}}}for(const n of f.nodes){{if(n.blockRef)continue;const p=snapWorldPoint(Number(n.x)||0,Number(n.y)||0);if(p.x!==n.x||p.y!==n.y){{n.x=p.x;n.y=p.y;moved++;syncCollapsedSectionPos(n.id,p.x,p.y)}}}}return moved}}
function snapLayout(){{if(world.querySelector('.node[data-node],.block-frame'))syncWorldCoordsFromDom();const f=view();snapLayoutPositions(f);persistViewToSource(f);appliedLayoutKey=f.key;render(false,viewAnchorCenter())}}
function resetLayout(){{clearSavedLayoutForCurrentView();restoreSourceLayout();appliedLayoutKey=null;skipSavedLayoutOnce=true;pendingSectionReflow=null;clearViewCache();clearSelection();fitMode='height';resetLayoutButton.textContent='✓';resetLayoutButton.style.borderColor='#79d8a6';setTimeout(()=>{{resetLayoutButton.textContent='↺';resetLayoutButton.style.borderColor=''}},1400);render(true)}}
const laidOutFlows=new Set();
const flow=()=>DATA.flows.find(f=>f.id===active);
const blockById=(id)=>(DATA.blocks||[]).find(b=>b.id===id);
function view(){{const b=blockView?blockById(blockView):null;if(b)return{{key:'block:'+b.id,nodes:b.view.nodes,edges:b.view.edges,frames:b.view.frames||[],islands:b.view.islands||[]}};const f=flow();if(blocksExpanded&&f.expanded){{const built=buildExpandedView(f);if(built)return built}}return{{key:f.id,nodes:f.nodes,edges:f.edges,frames:f.frames||[],islands:f.islands||[]}}}}
function openFlow(id){{active=id;blockView=null;clearSelection();appliedLayoutKey=null;collapsedSections.clear();render(false,null,false);requestAnimationFrame(()=>requestAnimationFrame(()=>focusFirstNodeInView()))}}
function openBlock(id){{if(!blockById(id))return;blockView=id;clearSelection();appliedLayoutKey=null;render(false,null,false);requestAnimationFrame(()=>requestAnimationFrame(()=>focusFirstNodeInView()))}}
function syncTools(){{const f=view(),hasSections=!!(f&&f.expanded),hasSinks=f.nodes.some(n=>isSinkNode(n));blocksButton.hidden=!!blockView||!hasSections;blocksButton.setAttribute('aria-pressed',String(blocksExpanded));blocksButton.style.borderColor=blocksExpanded?'#8eb8ff':'#8eb8ff55';blocksButton.textContent=blocksExpanded?'⊟ collapse sections':'⊞ expand sections';backButton.hidden=!blockView;sinksButton.hidden=!hasSinks;sinksButton.setAttribute('aria-pressed',String(sinksExpanded));sinksButton.style.borderColor=sinksExpanded?'#8eb8ff':'#8eb8ff55';sinksButton.title=sinksExpanded?'Show no-op sinks as null nodes':'Expand no-op sink cards';moveButton.setAttribute('aria-pressed',String(moving));moveButton.style.borderColor=moving?'#8eb8ff':'#8eb8ff55';moveButton.title=moving?'Dragging on — Shift/Cmd/Ctrl+click toggles selection':'Move mode — Shift/Cmd/Ctrl+click to multi-select';viewport.classList.toggle('move-mode',moving)}}
function nodeBox(n){{if(isSinkNode(n)&&!sinksExpanded)return{{w:n.w||72,h:72}};if(isStateNode(n))return{{w:n.w||220,h:n.h||52}};return{{w:340,h:null}}}}
function isSinkNode(n){{return !!n.sink}}
function isStateNode(n){{return !!n.state}}
function sinkTooltipHtml(n){{const body=splitNodeBody(n.brief),lines=[n.title||'No state change',...body.role,...body.steps.map(stripStepNumber)];return lines.filter(Boolean).map(line=>`<div>${{esc(line)}}</div>`).join('')}}
function esc(v){{const d=document.createElement('div');d.textContent=v;return d.innerHTML}}
function escAttr(v){{return esc(v).replace(/"/g,'&quot;').replace(/'/g,"&#39;")}}
function viewTitleText(){{if(blockView){{const b=blockById(blockView);return b?.title||''}}return flow()?.title||''}}
function viewTitleLayout(f){{let minX=GRID_ORIGIN,minY=GRID_ORIGIN;for(const n of f.nodes||[]){{const x=Number(n.x)||0,y=Number(n.y)||0;if(y<minY){{minY=y;minX=x}}else if(y===minY&&x<minX)minX=x}}return{{x:minX,y:Math.max(8,minY-56)}}}}
function viewTitleHtml(f){{const title=viewTitleText();if(!title)return'';const{{x,y}}=viewTitleLayout(f);return`<h2 class="view-title" style="left:${{x}}px;top:${{y}}px">${{esc(title)}}</h2>`}}
function renderList(){{FlowDrawer.update(drawer,DATA.flows,blockView?null:active,collapsed,openFlow,()=>{{collapsed=!collapsed;renderList();scheduleFit()}},{{blocks:DATA.blocks||[],activeBlock:blockView,onSelectBlock:openBlock}})}}
function frameHtml(frames){{return ''}}
function islandHtml(islands){{return (islands||[]).map(island=>{{const labelLeft=Number.isFinite(island.labelX)?island.labelX:ISLAND_LABEL_LEFT;return `<div class="island-section" data-island="${{escAttr(island.id)}}" style="left:${{island.x}}px;top:${{island.y}}px;width:${{island.width}}px;height:${{island.height}}px"><span class="island-section-label island-drag-label" data-island-drag="${{escAttr(island.id)}}" style="left:${{labelLeft}}px">${{esc(island.title)}}</span></div>`}}).join('')}}
function render(shouldFit=false,anchor=null,shouldFocusFirst=false){{expandedViewCache=null;const f=view();if(skipSavedLayoutOnce){{skipSavedLayoutOnce=false;appliedLayoutKey=f.key}}else applySavedLayout(f);renderedView=f;const right=Math.max(...f.nodes.map(n=>{{const box=nodeBox(n);return (n.x||0)+box.w}}),...(f.islands||[]).map(i=>i.x+i.width))+120,bottom=Math.max(...f.nodes.map(n=>(n.y||0)+(sinksExpanded&&n.sink?340:460)),...(f.islands||[]).map(i=>i.y+i.height))+120,canvasWidth=Math.max(1200,right),canvasHeight=Math.max(1000,bottom);world.style.width=canvasWidth+'px';world.style.height=canvasHeight+'px';const viewTitle=viewTitleHtml(f);world.innerHTML=`${{viewTitle}}<svg width="${{canvasWidth}}" height="${{canvasHeight}}" viewBox="0 0 ${{canvasWidth}} ${{canvasHeight}}"><defs><marker id="arrow" viewBox="0 0 14 10" markerWidth="18" markerHeight="15" refX="0" refY="5" markerUnits="userSpaceOnUse" orient="auto"><path d="M0,0 L0,10 L14,5 z" fill="#7aa7ff"/></marker></defs>${{f.edges.map(e=>{{const outputActive=nodeSelected(e.from),inputActive=nodeSelected(e.to),activeEdge=outputActive||inputActive,edgeState=outputActive?'active-output':inputActive?'active-input':'',labelState=outputActive?'active-output-label':inputActive?'active-input-label':'';return `<path class="edge ${{edgeState}} ${{activeEdge?'active-edge':''}}" data-from="${{e.from}}" data-to="${{e.to}}" marker-end="url(#arrow)"/><text class="edge-label ${{activeEdge?'active-label':''}} ${{labelState}}" data-label="${{e.from}}:${{e.to}}">${{esc(e.label)}}</text>`}}).join('')}}</svg>${{worldBodyHtml(f)}}`;try{{document.title=viewTitleText()||'{safe_title}'}}catch{{}}renderList();syncTools();wireNodes();wireSectionToggles();wireInfoTooltips();wireSinkTooltips();relayoutBoundaries(true);alignEdges();avoidEdgeLabels();requestAnimationFrame(()=>{{relayoutBoundaries(true);alignEdges();avoidEdgeLabels();finishSectionReflow();if(shouldFit)fit();else if(shouldFocusFirst)requestAnimationFrame(()=>requestAnimationFrame(()=>focusFirstNodeInView()));else if(anchor)restoreViewAnchor(anchor);else applyTransform()}})}}
function textLines(value){{return (Array.isArray(value)?value:[value??'']).flatMap(item=>String(item).split(/\\r?\\n/))}}
function sourceFile(value){{const raw=String(value??'').trim();const base=raw.replace(/\\\\/g,'/').split('/').pop()||raw;return base.split(':')[0]}}
function verifyList(items){{const lines=(items||[]).flatMap(item=>String(item).split(/\\r?\\n/)).map(line=>line.replace(/^[-•]\\s*/,'').trim()).filter(Boolean);if(!lines.length)return '';return `<ul>${{lines.map(line=>`<li>${{esc(line)}}</li>`).join('')}}</ul>`}}
function splitNodeBody(brief){{const lines=textLines(brief),role=[],steps=[];lines.forEach(line=>{{const text=String(line).trim();if(!text||text==='-')return;if(/^\\d+\\./.test(text))steps.push(text);else role.push(text)}});return{{role:role.slice(0,3),steps:steps.slice(0,5)}}}}
function stripStepNumber(line){{return String(line).replace(/^\\s*\\d+\\.\\s*/,'')}}
function sectionNode(n){{const isSelected=nodeSelected(n.id),isGroup=n.kind==='group',body=splitNodeBody(n.brief),roleHtml=body.role.length?`<div class="node-role">${{body.role.map(line=>`<span class="node-role-line">${{esc(line)}}</span>`).join('')}}</div>`:'',items=(n.preview||[]).slice(0,5),detailsHtml=items.length?`<ul class="node-details">${{items.map(line=>`<li>${{esc(line)}}</li>`).join('')}}</ul>`:'',badge=isGroup?`<span class="group-badge">group · ${{n.sectionCount||n.blockCount}}</span>`:`<span class="block-badge">block · ${{n.sectionCount||n.blockCount}}</span>`,openBtn=isGroup?'':`<button class="block-open" type="button" data-open-block="${{escAttr(n.sectionId||n.blockId)}}">open ↗</button>`,sectionCollapsed=!blocksExpanded||collapsedSections.has(n.id),titlePrefix=sectionCollapsed?'▸ ':'';return `<article class="node ${{isGroup?'group':'block'}} ${{isSelected?'selected':''}}" data-node="${{escAttr(n.id)}}" data-section="${{escAttr(n.sectionId||n.blockId||'')}}" data-block="${{escAttr(n.sectionId||n.blockId||'')}}" ${{nodePortAttr(n)}} style="${{nodePosStyle(n)}}"><div class="node-head"><h3 class="section-toggle" data-section-toggle="${{escAttr(n.id)}}">${{esc(titlePrefix+(n.title||''))}}</h3>${{badge}}</div>${{roleHtml}}<hr class="node-divider" aria-hidden="true">${{detailsHtml}}<hr class="node-divider" aria-hidden="true"><div class="node-footer"><small>${{esc(n.source)}}</small>${{openBtn}}</div></article>`}}
function sinkNode(n,origin){{const isSelected=nodeSelected(n.id),w=n.w||72;return `<article class="node sink-minimal ${{isSelected?'selected':''}}" data-node="${{escAttr(n.id)}}" data-sink="true" data-block-ref="${{escAttr(n.blockRef||'')}}" data-sink-html="${{escAttr(sinkTooltipHtml(n))}}" ${{nodePortAttr(n)}} style="${{nodePosStyle(n,origin)}}width:${{w}}px;" aria-label="${{escAttr(n.title||'No state change')}}"><span class="sink-mark" aria-hidden="true">⊗</span><h3>${{esc(n.title||'No state change')}}</h3></article>`}}
function toneClass(n){{const t=n.tone;return t==='dispatch'?'tone-dispatch':t==='callback'?'tone-callback':''}}
function toneBadge(n){{const t=n.tone;return t==='dispatch'?'<span class="tone-badge dispatch" title="Dispatch entry">⬡</span>':t==='callback'?'<span class="tone-badge callback" title="Event callback">⚡</span>':''}}
function stateNode(n,origin){{const isSelected=nodeSelected(n.id),w=n.w||220,h=n.h||52,tc=toneClass(n);return `<article class="node state-pill ${{tc}} ${{isSelected?'selected':''}}" data-node="${{escAttr(n.id)}}" data-block-ref="${{escAttr(n.blockRef||'')}}" ${{nodePortAttr(n)}} style="${{nodePosStyle(n,origin)}}width:${{w}}px;min-height:${{h}}px;height:${{h}}px"><div class="node-head"><h3>${{esc(n.title)}}</h3>${{toneBadge(n)}}</div></article>`}}
function node(n,origin){{if(n.kind==='block'||n.kind==='group')return sectionNode(n);if(isSinkNode(n)&&!sinksExpanded)return sinkNode(n,origin);if(isStateNode(n))return stateNode(n,origin);const isSelected=nodeSelected(n.id),process=n.kind==='process',body=splitNodeBody(n.brief),roleHtml=body.role.length?`<div class="node-role">${{body.role.map(line=>`<span class="node-role-line">${{esc(line)}}</span>`).join('')}}</div>`:'',detailsHtml=body.steps.length?`<ul class="node-details">${{body.steps.map(line=>`<li>${{esc(stripStepNumber(line))}}</li>`).join('')}}</ul>`:'',divider1=roleHtml&&detailsHtml?'<hr class="node-divider" aria-hidden="true">':'',verification=n.verification||[],verifyInfo=verification.length?`<button class="node-info" type="button" aria-label="Show verification notes" data-info-html="${{escAttr(verifyList(verification))}}">i</button>`:'';const frameClass=n.blockRef?'in-frame ':n.sectionScope==='group'?'from-group ':n.blockOrigin?'from-block ':'',sinkClass=isSinkNode(n)?'sink-card ':'';const box=nodeBox(n),widthStyle=isStateNode(n)&&box.w!==340?`width:${{box.w}}px;`:'';const tc=toneClass(n);return `<article class="node ${{sinkClass}}${{isSelected?'selected ':''}}${{process?'process ':''}}${{tc?tc+' ':''}}${{frameClass}}" data-node="${{n.id}}" data-sink="${{isSinkNode(n)?'true':'false'}}" data-block-ref="${{escAttr(n.blockRef||'')}}" ${{nodePortAttr(n)}} style="${{nodePosStyle(n,origin)}}${{widthStyle}}"><div class="node-head"><h3>${{esc(n.title)}}</h3>${{toneBadge(n)}}${{process?'<span class="process-mark" aria-label="process" role="img"></span>':''}}</div>${{roleHtml}}${{divider1}}${{detailsHtml}}<div class="node-footer"><small>${{esc(sourceFile(n.source))}}</small>${{verifyInfo}}</div></article>`}}
function isMultiSelectModifier(e){{return e.shiftKey||e.metaKey||e.ctrlKey}}
function isNodeActionTarget(e){{return!!(e.target.closest('.node-info')||e.target.closest('.block-open')||e.target.closest('.section-toggle')||e.target.closest('.section-frame-label')||e.target.closest('.island-drag-label'))}}
function dragTargets(){{const f=activeView();return[...selectedIds].map(id=>{{const n=f.nodes.find(x=>x.id===id),el=world.querySelector(`[data-node="${{id}}"]`);return n&&el?{{el,n,frame:null,island:null}}:null}}).filter(Boolean)}}
function wireNodes(){{world.querySelectorAll('[data-open-block]').forEach(button=>{{button.onclick=e=>{{e.stopPropagation();openBlock(button.dataset.openBlock)}};button.onpointerdown=e=>e.stopPropagation()}});world.querySelectorAll('.node').forEach(el=>{{el.onpointerdown=e=>{{e.stopPropagation();if(isNodeActionTarget(e))return;if(moving&&e.button===0){{const id=el.dataset.node;if(isMultiSelectModifier(e)){{toggleSelection(id);syncSelectionVisuals();return}}if(!selectedIds.has(id))setSingleSelection(id);const targets=dragTargets();if(!targets.length)return;syncSectionDragTargetsFromDom(targets);nodeState={{targets,start:sectionDragSnapshot(targets),x:e.clientX,y:e.clientY,moved:false,anchorEl:el}};el.setPointerCapture(e.pointerId)}}}};el.onpointermove=e=>{{if(!nodeState||nodeState.anchorEl!==el)return;const dx=(e.clientX-nodeState.x)/scale,dy=(e.clientY-nodeState.y)/scale;if(Math.abs(dx)+Math.abs(dy)>3)nodeState.moved=true;applySectionDragDelta(nodeState.start,dx,dy);alignEdges();resizeFrames();resizeIslands()}};el.onpointerup=e=>{{if(nodeState?.anchorEl===el){{const moved=nodeState.moved,targets=nodeState.targets;nodeState=null;try{{el.releasePointerCapture(e.pointerId)}}catch{{}}if(moved){{syncWorldCoordsFromDom();syncDragTargetsToSource(targets);relayoutBoundaries();alignEdges();return}}const id=el.dataset.node;if(isMultiSelectModifier(e))toggleSelection(id);else selectNodeById(id);return}}if(moving||e.button!==0||isNodeActionTarget(e))return;const id=el.dataset.node;if(isMultiSelectModifier(e))toggleSelection(id);else selectNodeById(id)}};el.ondblclick=e=>{{if(el.classList.contains('group')){{e.stopPropagation();blocksExpanded=true;blockView=null;clearSelection();appliedLayoutKey=null;render(false,null,true);return}}if(!el.dataset.block)return;e.stopPropagation();openBlock(el.dataset.block)}}}})}}
function wireInfoTooltips(){{let tooltip=document.getElementById('node-info-tooltip');if(!tooltip){{tooltip=document.createElement('div');tooltip.id='node-info-tooltip';tooltip.className='node-info-tooltip';tooltip.setAttribute('role','tooltip');document.body.appendChild(tooltip)}}tooltip.style.maxWidth='min(320px,70vw)';tooltip.style.overflowWrap='anywhere';const hide=()=>tooltip.classList.remove('visible'),overlap=(a,b)=>a.left<b.right&&a.right>b.left&&a.top<b.bottom&&a.bottom>b.top;world.querySelectorAll('.node-info').forEach(button=>{{const show=()=>{{tooltip.innerHTML=button.dataset.infoHtml||'';tooltip.classList.add('visible');const icon=button.getBoundingClientRect(),owner=button.closest('.node')?.getBoundingClientRect(),gap=10,width=tooltip.offsetWidth,height=tooltip.offsetHeight,candidates=[{{left:icon.right+gap,top:icon.top+(icon.height-height)/2}},{{left:icon.left-width-gap,top:icon.top+(icon.height-height)/2}},{{left:icon.left,top:icon.bottom+gap}},{{left:icon.left,top:icon.top-height-gap}}],fits=c=>c.left>=12&&c.top>=12&&c.left+width<=innerWidth-12&&c.top+height<=innerHeight-12,free=c=>!owner||!overlap({{left:c.left,top:c.top,right:c.left+width,bottom:c.top+height}},owner),chosen=candidates.find(c=>fits(c)&&free(c))||candidates.find(fits)||candidates[0],left=Math.max(12,Math.min(innerWidth-width-12,chosen.left)),top=Math.max(12,Math.min(innerHeight-height-12,chosen.top));tooltip.style.left=`${{left}}px`;tooltip.style.top=`${{top}}px`}};button.onpointerenter=show;button.onpointermove=show;button.onpointerleave=hide;button.onfocus=show;button.onblur=hide}})}};
function wireSinkTooltips(){{let tooltip=document.getElementById('sink-tooltip');if(!tooltip){{tooltip=document.createElement('div');tooltip.id='sink-tooltip';tooltip.className='sink-tooltip';tooltip.setAttribute('role','tooltip');document.body.appendChild(tooltip)}}const hide=()=>tooltip.classList.remove('visible');world.querySelectorAll('[data-sink="true"].sink-minimal').forEach(el=>{{const show=()=>{{tooltip.innerHTML=el.dataset.sinkHtml||'';tooltip.classList.add('visible');const rect=el.getBoundingClientRect(),left=Math.min(innerWidth-tooltip.offsetWidth-12,rect.right+10),top=Math.max(12,Math.min(innerHeight-tooltip.offsetHeight-12,rect.top+(rect.height-tooltip.offsetHeight)/2));tooltip.style.left=`${{left}}px`;tooltip.style.top=`${{top}}px`}};el.onpointerenter=show;el.onpointermove=show;el.onpointerleave=hide}});const activeId=[...selectedIds].find(id=>{{const el=world.querySelector(`[data-node="${{id}}"]`);return el?.dataset.sink==='true'&&el.classList.contains('sink-minimal')}});if(activeId){{const el=world.querySelector(`[data-node="${{activeId}}"]`),activeTooltip=document.getElementById('sink-tooltip');if(el&&activeTooltip){{activeTooltip.innerHTML=el.dataset.sinkHtml||'';activeTooltip.classList.add('visible');const rect=el.getBoundingClientRect();activeTooltip.style.left=`${{Math.min(innerWidth-activeTooltip.offsetWidth-12,rect.right+10)}}px`;activeTooltip.style.top=`${{Math.max(12,rect.top+(rect.height-activeTooltip.offsetHeight)/2)}}px`}}}}else hide()}}
function layoutRows(){{const f=view(),rowGap=180,boxes=[...world.querySelectorAll('.node')];if(!boxes.length)return;const columnStep=520,columnFor=left=>Math.round(((Number.parseFloat(left)||0)-70)/columnStep),columns=new Map();boxes.forEach(box=>{{const col=columnFor(box.style.left);if(!columns.has(col))columns.set(col,[]);columns.get(col).push(box)}});columns.forEach(columnBoxes=>{{const placed=[];columnBoxes.sort((a,b)=>(Number.parseFloat(a.style.top)||0)-(Number.parseFloat(b.style.top)||0));columnBoxes.forEach(box=>{{let top=Number.parseFloat(box.style.top)||0;const height=box.offsetHeight||0;let bumped=true;while(bumped){{bumped=false;for(const other of placed){{if(top+height+rowGap>other.top&&top<other.bottom+rowGap){{const candidate=other.bottom+rowGap;if(candidate>top){{top=candidate;bumped=true}}}}}}}}box.style.top=`${{top}}px`;const n=f.nodes.find(item=>item.id===box.dataset.node);if(n)n.y=top;placed.push({{top,bottom:top+height}});placed.sort((a,b)=>a.top-b.top)}});}});relayoutBoundaries()}}
function elementDomBounds(el){{const x=Number.parseFloat(el.style.left),y=Number.parseFloat(el.style.top),left=Number.isFinite(x)?x:el.offsetLeft,top=Number.isFinite(y)?y:el.offsetTop,w=el.classList.contains('block-frame')?(el.offsetWidth||Number.parseFloat(el.style.width)||340):(Number.parseFloat(el.style.width)||el.offsetWidth||340),h=el.classList.contains('block-frame')?(el.offsetHeight||Number.parseFloat(el.style.height)||130):(Number.parseFloat(el.style.height)||el.offsetHeight||130);return{{left,top,right:left+w,bottom:top+h}}}}
function worldElementBounds(el){{return worldBox(el)}}
function fitDomBounds(elements,pad){{const padding=typeof pad==='number'?{{left:pad,top:pad,right:pad,bottom:pad}}:pad;if(!elements.length)return null;const boxes=elements.map(elementDomBounds),minX=Math.min(...boxes.map(b=>b.left))-padding.left,minY=Math.min(...boxes.map(b=>b.top))-padding.top,maxX=Math.max(...boxes.map(b=>b.right))+padding.right,maxY=Math.max(...boxes.map(b=>b.bottom))+padding.bottom;return{{x:minX,y:minY,width:maxX-minX,height:maxY-minY}}}}
function applyDomBounds(el,bounds){{el.style.left=`${{bounds.x}}px`;el.style.top=`${{bounds.y}}px`;el.style.width=`${{bounds.width}}px`;el.style.height=`${{bounds.height}}px`}}
function applyFrameBounds(el,frame,bounds){{frame.x=bounds.x;frame.y=bounds.y;frame.width=bounds.width;frame.height=bounds.height;applyDomBounds(el,bounds)}}
function applyIslandBounds(el,island,bounds){{island.x=bounds.x;island.y=bounds.y;island.width=bounds.width;island.height=bounds.height;applyDomBounds(el,bounds)}}
function frameMemberIdSet(frame,nodes){{return new Set(nodes.filter(n=>n.blockRef===frame.id).map(n=>n.id))}}
function domNodesByIds(ids){{return[...world.querySelectorAll('.node')].filter(el=>ids.has(el.dataset.node))}}
function buildFrameChildren(frames){{const children=new Map();for(const frame of frames||[]){{if(!frame.parent)continue;if(!children.has(frame.parent))children.set(frame.parent,[]);children.get(frame.parent).push(frame.id)}}return children}}
function frameDepth(frameId,children){{const kids=children.get(frameId)||[];if(!kids.length)return 0;return 1+Math.max(...kids.map(id=>frameDepth(id,children)))}}
function frameMemberBounds(el,members,padding){{const memberWorld=members.map(m=>worldBox(m));return{{contentMinX:Math.min(...memberWorld.map(b=>b.x)),contentMinY:Math.min(...memberWorld.map(b=>b.y)),contentMaxX:Math.max(...memberWorld.map(b=>b.right)),contentMaxY:Math.max(...memberWorld.map(b=>b.bottom))}}}}
function resizeOneFrame(frame,children,padding){{const el=world.querySelector(`[data-frame="${{frame.id}}"]`);if(!el)return false;const frameById=frameByIdMap(activeView().frames||[]),parentOrigin=frameParentWorldOrigin(frame,frameById),members=frameDirectChildren(el),minW=padding.left+padding.right+120,minH=padding.top+padding.bottom+72;if(!members.length){{const frameWorld=worldBox(el),anchorX=frameWorld.x,anchorY=frameWorld.y,width=Math.max(minW,frame.width||minW),height=Math.max(minH,frame.height||minH);if(frame.width!==width||frame.height!==height||el.style.width!==`${{width}}px`||el.style.height!==`${{height}}px`){{frame.x=anchorX;frame.y=anchorY;frame.width=width;frame.height=height;el.style.left=`${{anchorX-parentOrigin.x}}px`;el.style.top=`${{anchorY-parentOrigin.y}}px`;el.style.width=`${{width}}px`;el.style.height=`${{height}}px`;return true}}return false}}const memberWorld=members.map(m=>worldBox(m)),{{contentMinX,contentMinY,contentMaxX,contentMaxY}}=frameMemberBounds(el,members,padding),newAnchorX=contentMinX-padding.left,newAnchorY=contentMinY-padding.top,width=Math.max(minW,contentMaxX-newAnchorX+padding.right),height=Math.max(minH,contentMaxY-newAnchorY+padding.bottom),prevW=frame.width,prevH=frame.height,prevX=frame.x,prevY=frame.y;frame.x=newAnchorX;frame.y=newAnchorY;frame.width=width;frame.height=height;el.style.left=`${{newAnchorX-parentOrigin.x}}px`;el.style.top=`${{newAnchorY-parentOrigin.y}}px`;el.style.width=`${{width}}px`;el.style.height=`${{height}}px`;for(let i=0;i<members.length;i++){{const w=memberWorld[i];members[i].style.left=`${{w.x-newAnchorX}}px`;members[i].style.top=`${{w.y-newAnchorY}}px`}}return prevW!==width||prevH!==height||prevX!==newAnchorX||prevY!==newAnchorY}}
function resizeFrames(){{const f=activeView(),frames=f.frames||[];if(!frames.length)return;const children=buildFrameChildren(frames),padding={{left:FRAME_PAD,top:FRAME_PAD+FRAME_LABEL_PAD,right:FRAME_PAD,bottom:FRAME_PAD}},sorted=[...frames].sort((a,b)=>frameDepth(a.id,children)-frameDepth(b.id,children));for(let pass=0;pass<6;pass++){{let changed=false;for(const frame of sorted){{if(resizeOneFrame(frame,children,padding))changed=true}}if(!changed)break}}syncWorldCoordsFromDom()}}
function islandIndexFromId(islandId){{const match=String(islandId).match(/-island-(\\d+)$/);return match?Number.parseInt(match[1],10)-1:null}}
function resizeIslands(){{const f=activeView();(f.islands||[]).forEach(island=>{{const el=world.querySelector(`[data-island="${{island.id}}"]`);if(!el)return;const islandIndex=islandIndexFromId(island.id);if(islandIndex===null)return;const memberIds=new Set(f.nodes.filter(n=>n.island===islandIndex).map(n=>n.id)),members=domNodesByIds(memberIds),islandFrames=[...world.querySelectorAll('.block-frame')].filter(frameEl=>{{const meta=(f.frames||[]).find(fr=>fr.id===frameEl.dataset.frame);return meta&&meta.island===islandIndex}}),bounds=fitDomBounds([...members,...islandFrames],{{left:24,top:44,right:24,bottom:24}});if(!bounds)return;bounds.width=Math.max(bounds.width,800);applyIslandBounds(el,island,bounds)}})}}
function relayoutBoundaries(recalcFrames=true){{if(recalcFrames){{resizeFrames();resizeIslands()}}resizeWorld()}}
function resizeWorld(){{const items=[...world.querySelectorAll('.node'),...world.querySelectorAll('.block-frame'),...world.querySelectorAll('.island-section')];if(!items.length)return;const boxes=items.map(worldBox),width=Math.max(1200,Math.max(...boxes.map(b=>b.right))+120),height=Math.max(1000,Math.max(...boxes.map(b=>b.bottom))+120);world.style.width=width+'px';world.style.height=height+'px';const svg=world.querySelector('svg');if(svg){{svg.setAttribute('width',width);svg.setAttribute('height',height);svg.setAttribute('viewBox',`0 0 ${{width}} ${{height}}`)}}}}
function nodePortAttr(n){{return `data-in-ports="top,left" data-out-ports="bottom,right"`}}
const PORT_SIDE_SETS={{in:['top','left'],out:['bottom','right']}};
function nodePortSides(el,kind){{const allowed=PORT_SIDE_SETS[kind],attr=kind==='out'?el?.dataset?.outPorts:el?.dataset?.inPorts,parsed=(attr||'').split(',').map(s=>s.trim()).filter(s=>allowed.includes(s));return parsed.length?parsed:allowed}}
function alignEdges(){{const gap=6,arrowLength=18,port=(boxEl,side,kind,index=0,count=1)=>{{const box=worldBox(boxEl),x=box.x,y=box.y,w=box.w,h=box.h,offset=(index-(count-1)/2)*18,s={{top:{{p:[x+w/2+offset,y-gap],t:kind==='out'?[0,-1]:[0,1]}},left:{{p:[x-gap,y+h/2+offset],t:kind==='out'?[-1,0]:[1,0]}},bottom:{{p:[x+w/2+offset,y+h+gap],t:kind==='out'?[0,1]:[0,-1]}},right:{{p:[x+w+gap,y+h/2+offset],t:kind==='out'?[1,0]:[-1,0]}}}}[side];return {{x:s.p[0],y:s.p[1],t:s.t}}}};const items=[];world.querySelectorAll('.edge[data-from]').forEach(path=>{{const a=world.querySelector(`[data-node="${{path.dataset.from}}"]`),b=world.querySelector(`[data-node="${{path.dataset.to}}"]`),orphanLabel=world.querySelector(`[data-label="${{path.dataset.from}}:${{path.dataset.to}}"]`);if(!a||!b){{path.style.display='none';if(orphanLabel)orphanLabel.style.display='none';return}}path.style.display='';if(orphanLabel)orphanLabel.style.display='';const outSides=nodePortSides(a,'out'),inSides=nodePortSides(b,'in');let best=null;for(const outSide of outSides)for(const inSide of inSides){{const out=port(a,outSide,'out'),input=port(b,inSide,'in'),distance=Math.hypot(input.x-out.x,input.y-out.y);if(!best||distance<best.distance)best={{outSide,inSide,distance}}}}items.push({{path,a,b,outSide:best.outSide,inSide:best.inSide}})}});const counts=new Map(),key=(id,kind,side)=>`${{id}}:${{kind}}:${{side}}`;items.forEach(item=>{{for(const [id,kind,side] of [[item.path.dataset.from,'out',item.outSide],[item.path.dataset.to,'in',item.inSide]])counts.set(key(id,kind,side),(counts.get(key(id,kind,side))||0)+1)}});const outSlots=new Map(),inSlots=new Map(),assignSlots=(kind,slots)=>{{const groups=new Map();items.forEach(item=>{{const side=kind==='out'?item.outSide:item.inSide,id=kind==='out'?item.path.dataset.from:item.path.dataset.to,edgeId=`${{item.path.dataset.from}}:${{item.path.dataset.to}}`,axis=kind==='out'?(side==='top'||side==='bottom'?worldBox(item.b).x+worldBox(item.b).w/2:worldBox(item.b).y+worldBox(item.b).h/2):(side==='top'||side==='bottom'?worldBox(item.a).x+worldBox(item.a).w/2:worldBox(item.a).y+worldBox(item.a).h/2),groupKey=key(id,kind,side);if(!groups.has(groupKey))groups.set(groupKey,[]);groups.get(groupKey).push({{edgeId,axis}})}});groups.forEach(group=>group.sort((a,b)=>a.axis-b.axis).forEach((entry,index)=>slots.set(entry.edgeId,index)))}};assignSlots('out',outSlots);assignSlots('in',inSlots);items.forEach(item=>{{const edgeId=`${{item.path.dataset.from}}:${{item.path.dataset.to}}`,outKey=key(item.path.dataset.from,'out',item.outSide),inKey=key(item.path.dataset.to,'in',item.inSide),out=port(item.a,item.outSide,'out',outSlots.get(edgeId)||0,counts.get(outKey)),input=port(item.b,item.inSide,'in',inSlots.get(edgeId)||0,counts.get(inKey)),end={{x:input.x-input.t[0]*arrowLength,y:input.y-input.t[1]*arrowLength}},axisGap=Math.max(Math.abs(end.x-out.x),Math.abs(end.y-out.y)),distance=Math.max(48,Math.min(150,axisGap*.35)),c1x=out.x+out.t[0]*distance,c1y=out.y+out.t[1]*distance,c2x=end.x-input.t[0]*distance,c2y=end.y-input.t[1]*distance;item.path.setAttribute('d',`M${{out.x}},${{out.y}} C${{c1x}},${{c1y}} ${{c2x}},${{c2y}} ${{end.x}},${{end.y}}`);const label=world.querySelector(`[data-label="${{item.path.dataset.from}}:${{item.path.dataset.to}}"]`);if(label){{label.setAttribute('x',(out.x+end.x)/2-25);label.setAttribute('y',(out.y+end.y)/2-6)}}}})}}
function avoidEdgeLabels(){{const labels=[...world.querySelectorAll('.edge-label')].filter(label=>label.style.display!=='none'),boxes=[...world.querySelectorAll('.node')].map(el=>{{const b=worldBox(el);return{{x:b.x-8,y:b.y-8,right:b.right+8,bottom:b.bottom+8}}}});for(let pass=0;pass<12;pass++){{let moved=false;for(let i=0;i<labels.length;i++){{const label=labels[i],rect=label.getBBox();const blocked=boxes.some(box=>rect.x<box.right&&rect.x+rect.width>box.x&&rect.y<box.bottom&&rect.y+rect.height>box.y);const overlapped=labels.slice(0,i).some(other=>{{const otherRect=other.getBBox();return rect.x<otherRect.x+otherRect.width+8&&rect.x+rect.width+8>otherRect.x&&rect.y<otherRect.y+otherRect.height+8&&rect.y+rect.height+8>otherRect.y}});if(blocked||overlapped){{label.setAttribute('y',Number(label.getAttribute('y'))+20);moved=true}}}}if(!moved)break}}}}
function applyTransform(){{world.style.transform=`translate(${{panX}}px,${{panY}}px) scale(${{scale}})`;const gridStep=GRID_CELL*scale;viewport.style.backgroundSize=`${{gridStep}}px ${{gridStep}}px`;viewport.style.backgroundPosition=`${{panX}}px ${{panY}}px`;syncFitButtonLabel()}}
function viewportPoint(clientX,clientY){{const rect=viewport.getBoundingClientRect();return{{x:clientX-rect.left,y:clientY-rect.top}}}}
function captureViewAnchor(clientX,clientY){{const p=viewportPoint(clientX,clientY);return{{sx:p.x,sy:p.y,wx:(p.x-panX)/scale,wy:(p.y-panY)/scale}}}}
function viewAnchorCenter(){{const rect=viewport.getBoundingClientRect();return captureViewAnchor(rect.left+rect.width/2,rect.top+rect.height/2)}}
function restoreViewAnchor(anchor){{if(!anchor)return;panX=anchor.sx-anchor.wx*scale;panY=anchor.sy-anchor.wy*scale;fitMode='manual';applyTransform()}}
function fit(){{cancelPanAnimation();const nodes=[...world.querySelectorAll('.node')];if(!nodes.length)return;const boxes=nodes.map(worldBox),minX=Math.min(...boxes.map(b=>b.x)),minY=Math.min(...boxes.map(b=>b.y)),maxX=Math.max(...boxes.map(b=>b.right)),maxY=Math.max(...boxes.map(b=>b.bottom)),w=Math.max(maxX-minX,1),h=Math.max(maxY-minY,1),left=drawerInset(),free=Math.max(viewport.clientWidth-left-24,120),freeH=Math.max(viewport.clientHeight-48,120),widthScale=free/w,heightScale=freeH/h;if(fitMode!=='manual'){{const next=fitMode==='width'?widthScale:Math.min(widthScale,heightScale);scale=Math.max(.35,Math.min(1.5,next))}}panX=left+(free-w*scale)/2-minX*scale;panY=24+(freeH-h*scale)/2-minY*scale;applyTransform()}}
blocksButton.onclick=()=>{{const anchor=viewAnchorCenter();blocksExpanded=!blocksExpanded;collapsedSections.clear();clearSelection();appliedLayoutKey=null;fitMode='manual';laidOutFlows.clear();render(false,anchor)}};sinksButton.onclick=()=>{{const anchor=viewAnchorCenter();sinksExpanded=!sinksExpanded;saveSinksExpanded();clearSelection();appliedLayoutKey=null;fitMode='manual';laidOutFlows.clear();render(false,anchor)}};backButton.onclick=()=>{{blockView=null;clearSelection();appliedLayoutKey=null;render(false,null,true)}};
fitButton.onclick=()=>cycleFitMode();fitButton.title='Cycle zoom: fit width → fit height → 100%';snapButton.onclick=()=>snapLayout();resetLayoutButton.onclick=()=>resetLayout();saveLayoutButton.onclick=()=>saveLayout();moveButton.onclick=()=>{{moving=!moving;syncTools()}};moveButton.title='Move mode — Shift/Cmd/Ctrl+click to multi-select';viewport.onpointerdown=e=>{{if(e.target.closest('#tools'))return;cancelPanAnimation();if(!e.target.closest('.node'))focusFlowViewport();if(e.target.closest('.node'))return;panState={{x:e.clientX,y:e.clientY,panX,panY,moved:false,deselectOnClick:!e.shiftKey&&!e.metaKey&&!e.ctrlKey}};viewport.classList.add('panning');viewport.setPointerCapture(e.pointerId)}};viewport.onpointermove=e=>{{if(!panState)return;if(Math.abs(e.clientX-panState.x)+Math.abs(e.clientY-panState.y)>3)panState.moved=true;panX=panState.panX+e.clientX-panState.x;panY=panState.panY+e.clientY-panState.y;applyTransform()}};viewport.onpointerup=e=>{{if(!panState)return;const moved=panState.moved,deselectOnClick=panState.deselectOnClick;panState=null;viewport.classList.remove('panning');try{{viewport.releasePointerCapture(e.pointerId)}}catch{{}}if(!moved&&deselectOnClick&&selectedIds.size){{clearSelection();syncSelectionVisuals()}}}};document.addEventListener('keydown',e=>{{if(e.key==='Escape'&&selectedIds.size){{clearSelection();syncSelectionVisuals();return}}if(e.key==='Tab'&&!e.shiftKey&&document.activeElement===viewport&&!e.altKey&&!e.ctrlKey&&!e.metaKey){{e.preventDefault();FlowDrawer.focusActiveItem(drawer);return}}const dir=navKeyDirection(e.key);if(!dir)return;if(e.altKey||e.ctrlKey||e.metaKey)return;const activeTag=document.activeElement?.tagName;if(activeTag==='INPUT'||activeTag==='TEXTAREA'||activeTag==='SELECT')return;if(document.activeElement?.isContentEditable)return;const inDrawer=!!e.target.closest?.('#drawer');if(inDrawer&&(dir==='up'||dir==='down')){{e.preventDefault();FlowDrawer.stepFlowSelection(drawer,dir==='up'?-1:1);return}}if(e.target.closest?.('#tools'))return;e.preventDefault();focusFlowViewport();navigateSelection(dir)}});viewport.onwheel=e=>{{e.preventDefault();cancelPanAnimation();const rect=viewport.getBoundingClientRect(),cursorX=e.clientX-rect.left,cursorY=e.clientY-rect.top,worldX=(cursorX-panX)/scale,worldY=(cursorY-panY)/scale,unit=e.deltaMode===1?16:e.deltaMode===2?viewport.clientHeight:1,delta=Math.max(-120,Math.min(120,e.deltaY*unit)),nextScale=Math.max(.35,Math.min(1.5,scale-delta*0.001));panX=cursorX-worldX*nextScale;panY=cursorY-worldY*nextScale;scale=nextScale;fitMode='manual';saveZoom();applyTransform()}};focusFlowViewport();render(false,null,true);
</script></body></html>'''


def main() -> None:
    parser = argparse.ArgumentParser(description="Render data-only Logic Flow JSON to standalone HTML")
    parser.add_argument("source", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--title", default="Logic Flow")
    args = parser.parse_args()
    data = json.loads(args.source.read_text(encoding="utf-8"))
    prepare_layout(data)
    args.output.write_text(render(data, args.title), encoding="utf-8")
    blocks = len(data.get("blocks") or [])
    print(f"rendered {len(data['flows'])} flow(s) and {blocks} block(s) to {args.output}")


if __name__ == "__main__":
    main()
