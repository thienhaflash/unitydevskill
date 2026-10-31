#!/usr/bin/env python3
"""Extract a Logic Flow .flow source file into data-only JSON.

This script deliberately performs no layout, sizing, styling, or HTML generation.
"""

import argparse
import json
import re
import sys
from pathlib import Path

from render_flow import is_noop_node, parse_graph, split_node_body

_TRANSITION_TITLE = re.compile(
    r"\b(APP_[A-Z0-9_]+|TileStatus\.[A-Za-z]+)\s+to\s+(APP_[A-Z0-9_]+|TileStatus\.[A-Za-z]+)\b",
    re.IGNORECASE,
)
_DECISION_HINT = re.compile(r"\b(dispatch|decision|gate|entry)\b", re.IGNORECASE)
_ROUTING_ACTION_NO_STEPS = _DECISION_HINT  # routing ACTION nodes must have zero steps
_TRANSITION_STEP = re.compile(r"\btransition(s)?\s+to\s+APP_", re.IGNORECASE)
_SOURCE_LINE_NUMBERS = re.compile(r":\d")
_MAX_STEPS = 5
_MAX_VERIFY_CHARS = 140


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _step_number(line: str) -> int | None:
    match = re.match(r"^\s*(\d+)\.", str(line))
    return int(match.group(1)) if match else None


def _source_filename(source: str) -> str:
    base = str(source or "").strip().replace("\\", "/").split("/")[-1]
    return base.split(":")[0].strip()


SECTION_KINDS = frozenset({"block", "group"})


def _iter_graph_nodes(container: dict):
    """Flow/block nodes plus nodes declared inside flow-local groups."""
    scope = container["id"]
    for node in container["nodes"]:
        yield scope, node
    for group in container.get("groups") or []:
        group_scope = f"{scope}.{group['id']}"
        for node in group["nodes"]:
            yield group_scope, node


def _title_triples(container: dict) -> set[tuple[str, str, str]]:
    """Title triples along edges, used to spot sequences that belong in a block."""
    titles = {node["id"]: node["title"] for node in container["nodes"] if node.get("kind") not in SECTION_KINDS}
    outgoing: dict[str, list[str]] = {}
    for edge in container["edges"]:
        outgoing.setdefault(edge["from"], []).append(edge["to"])
    triples = set()
    for first in titles:
        for second in outgoing.get(first, []):
            if second not in titles or second == first:
                continue
            for third in outgoing.get(second, []):
                if third not in titles or third in {first, second}:
                    continue
                triples.add((titles[first], titles[second], titles[third]))
    return triples


def lint_blocks(data: dict) -> list[str]:
    issues: list[str] = []
    blocks = data.get("blocks") or []
    containers = blocks + data["flows"]
    used = {node.get("block") for container in containers for node in container["nodes"] if node.get("kind") == "block"}
    for flow in data["flows"]:
        group_ids = {group["id"] for group in flow.get("groups") or []}
        used_groups = {node.get("group") for node in flow["nodes"] if node.get("kind") == "group"}
        for group in flow.get("groups") or []:
            if group["id"] not in used_groups:
                issues.append(f"flow {flow['id']}: group '{group['id']}' is declared but never used — add usegroup or delete it")
            if len(group["nodes"]) < 2:
                issues.append(f"flow {flow['id']}: group '{group['id']}' only has {len(group['nodes'])} node(s)")
        for missing in used_groups - group_ids:
            if missing:
                issues.append(f"flow {flow['id']}: usegroup references unknown group '{missing}'")

    seen: dict[tuple[str, str, str], list[str]] = {}
    for container in containers:
        for triple in _title_triples(container):
            seen.setdefault(triple, []).append(container["id"])
    repeats = sorted((where, triple) for triple, where in seen.items() if len(set(where)) > 1)
    for where, triple in repeats[:5]:
        chain = " -> ".join(triple)
        issues.append(f"duplicate sequence in {', '.join(sorted(set(where)))}: {chain} — extract a shared block")
    return issues


def lint_graph(data: dict) -> list[str]:
    issues: list[str] = lint_blocks(data)
    for flow in (data.get("blocks") or []) + data["flows"]:
        for fid, node in _iter_graph_nodes(flow):
            if node.get("kind") in SECTION_KINDS:
                continue
            nid = node["id"]
            title = node["title"]
            brief = node["brief"]
            role, steps = split_node_body(brief)
            header = role  # legacy name in checks below

            if is_noop_node(node):
                issues.append(
                    f"{fid}:{nid}: no-op node '{title}' — delete the node; record early returns on verify lines of the nearest ACTION"
                )
                continue

            if _TRANSITION_TITLE.search(title):
                issues.append(
                    f"{fid}:{nid}: transition in title '{title}' — use state nodes + edge labels instead"
                )

            if header:
                if _norm(header[0]) == _norm(title):
                    issues.append(f"{fid}:{nid}: brief repeats title '{title}' — set brief to '-'")
                for line in header:
                    if _norm(line) == _norm(title):
                        issues.append(f"{fid}:{nid}: brief line repeats title '{title}'")

            if steps:
                first = re.sub(r"^\s*\d+\.\s*", "", steps[0])
                if _norm(first) == _norm(title) or (header and _norm(first) == _norm(header[0])):
                    issues.append(
                        f"{fid}:{nid}: first step repeats title/brief — drop duplicate text"
                    )
                for step in steps:
                    if _TRANSITION_STEP.search(step):
                        issues.append(
                            f"{fid}:{nid}: step describes a transition — use edge + state node: {step[:60]}"
                        )

            if steps and _ROUTING_ACTION_NO_STEPS.search(title):
                issues.append(
                    f"{fid}:{nid}: routing ACTION '{title}' has step lines — move guards to edges"
                )

            if len(role) > 3:
                issues.append(f"{fid}:{nid}: {len(role)} role lines — max 3 in brief field")

            if len(steps) > _MAX_STEPS:
                issues.append(
                    f"{fid}:{nid}: {len(steps)} steps — max {_MAX_STEPS}; split into chained ACTION nodes"
                )
            for step in steps:
                num = _step_number(step)
                if num is not None and (num < 1 or num > _MAX_STEPS):
                    issues.append(f"{fid}:{nid}: step number {num} out of range 1..{_MAX_STEPS}")

            source = str(node.get("source") or "")
            if "/" in source.replace("\\", "/") or _SOURCE_LINE_NUMBERS.search(source):
                issues.append(
                    f"{fid}:{nid}: source must be filename only — use '{_source_filename(source)}'"
                )

            for hint in node.get("verification") or []:
                text = str(hint).strip()
                if not text:
                    continue
                if len(text) > _MAX_VERIFY_CHARS:
                    issues.append(
                        f"{fid}:{nid}: verify hint too long ({len(text)} chars) — split into multiple verify lines"
                    )
                if re.search(r"[.!?]\s+\S", text):
                    issues.append(
                        f"{fid}:{nid}: verify hint looks like a paragraph — one fact per verify line"
                    )

    return issues


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract Logic Flow text into data-only JSON")
    parser.add_argument("source", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument(
        "--lint",
        action="store_true",
        help="Report authoring issues (duplicates, transitions, step count, source, verify hints)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when --lint finds issues",
    )
    args = parser.parse_args()
    data = parse_graph(args.source)

    if args.lint or args.strict:
        issues = lint_graph(data)
        for issue in issues:
            print(f"lint: {issue}", file=sys.stderr)
        if issues:
            print(f"lint: {len(issues)} issue(s)", file=sys.stderr)
            if args.strict:
                sys.exit(1)
        else:
            print("lint: ok", file=sys.stderr)

    if args.output:
        # Block-reference cards are derived from the block itself at render time,
        # so only the reference itself is data.
        derived = ("x", "y", "title", "brief", "source", "certainty", "blockId", "blockCount", "preview")
        for container in (data.get("blocks") or []) + data["flows"]:
            for node in container["nodes"]:
                node.pop("x", None)
                node.pop("y", None)
                if node.get("kind") not in SECTION_KINDS:
                    continue
                for key in derived:
                    node.pop(key, None)
                if not node.get("note"):
                    node.pop("note", None)
                for key in ("stories", "verification"):
                    if not node.get(key):
                        node.pop(key, None)
        args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        blocks = len(data.get("blocks") or [])
        print(f"extracted {len(data['flows'])} flow(s) and {blocks} block(s) to {args.output}")
    elif not args.lint:
        parser.error("provide -o/--output or --lint")


if __name__ == "__main__":
    main()
