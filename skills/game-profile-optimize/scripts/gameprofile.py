#!/usr/bin/env python3
"""Find and read the profile of the game being measured. Nothing game-specific lives in the skill: the profile, the readings and the notes live in the
project that is measured, in <repo>/.claude/perf/<game>/ (override the folder with PERF_DIR).

usage: gameprofile.py <game|-> <dotted.key> [default]   (prints strings as they are, other values as JSON; "-" = the only game of the repo)
       gameprofile.py <game|-> --dir                    (prints the perf folder)
Imported by the other python scripts: load(game), perf_dir(game), devices().
"""
import json, os, subprocess, sys

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def repo_root():
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("gameprofile.py: not inside a git checkout; run from the game's repo or set PERF_DIR to the perf folder")
    return r.stdout.strip()


def perf_dir(game=None):
    d = os.environ.get("PERF_DIR")
    if d:
        return d
    base = os.path.join(repo_root(), ".claude", "perf")
    if game and game != "-":
        return os.path.join(base, game)
    games = sorted(g for g in (os.listdir(base) if os.path.isdir(base) else []) if os.path.exists(os.path.join(base, g, "profile.json")))
    if len(games) == 1:
        return os.path.join(base, games[0])
    sys.exit(f"gameprofile.py: pick a game with GAME=<id> (profiles under {base}: {', '.join(games) or 'none; see reference/harness-protocol.md, Adding a game'})")


def load(game=None):
    p = os.path.join(perf_dir(game), "profile.json")
    if not os.path.exists(p):
        sys.exit(f"gameprofile.py: no {p}; copy examples/profile.example.json there and fill it in")
    return json.load(open(p))


def data_dir(game=None):
    return perf_dir(game)


def devices(game=None):
    p = os.path.join(perf_dir(game), "devices.json")
    return json.load(open(p if os.path.exists(p) else os.path.join(SKILL, "devices.default.json")))


if __name__ == "__main__":
    g = sys.argv[1]
    if sys.argv[2] == "--dir":
        print(perf_dir(g))
        sys.exit(0)
    v = load(g)
    for part in sys.argv[2].split("."):
        v = v.get(part) if isinstance(v, dict) else None
    if v is None:
        print(sys.argv[3] if len(sys.argv) > 3 else "")
    else:
        print(v if isinstance(v, str) else json.dumps(v))
