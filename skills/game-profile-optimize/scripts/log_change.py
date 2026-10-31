#!/usr/bin/env python3
"""Record a build or an optimization in the data store, so "Change over the builds" and "What each optimization did" fill themselves.

usage (GAME=<id> or --game <id> when the repo has several games):
  log_change.py build  --id "Depth prepass" --desc "what this build contains" [--commit <sha>] [--date YYYY-MM-DD]
  log_change.py effect --change "what was changed" --kind Shader|Settings|Engine|Content|Import|Draw order|Power --effect "measured effect, with numbers"
                       --result kept|no|try [--build <build id>]
  result: kept = adopted, no = measured, no gain or rejected, try = measured upper bound (not a change in the game)
Run it once per build after build-install.sh, and once per optimization right after its A/B is validated. An effect without numbers is not an effect.
"""
import argparse, json, os, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gameprofile as P


def append(name, row, key):
    p = os.path.join(P.perf_dir(a.game), name)
    rows = json.load(open(p))
    rows = [r for r in rows if r.get(key) != row[key]]  # logging the same build or change again replaces it
    rows.append(row)
    json.dump(rows, open(p, "w"), indent=1)


ap = argparse.ArgumentParser()
ap.add_argument("--game", default=os.environ.get("GAME"))
sub = ap.add_subparsers(dest="what", required=True)
b = sub.add_parser("build")
b.add_argument("--id", required=True)
b.add_argument("--desc", required=True)
b.add_argument("--commit")
b.add_argument("--date")
e = sub.add_parser("effect")
e.add_argument("--change", required=True)
e.add_argument("--kind", required=True)
e.add_argument("--effect", required=True)
e.add_argument("--result", required=True, choices=["kept", "no", "try"])
e.add_argument("--build")
a = ap.parse_args()
if not a.game:
    sys.exit('log_change.py: pass --game <id> or set GAME')
if a.what == "build":
    commit = a.commit or subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    append("builds.json", {"id": a.id, "desc": a.desc, "commit": commit, "date": a.date or time.strftime("%Y-%m-%d")}, "id")
else:
    append("effects.json", {"change": a.change, "kind": a.kind, "effect": a.effect, "result": a.result, "build": a.build}, "change")
    # "try" rows are upper bounds, "no" rows are rejections: both stay in the table on purpose
print("logged", a.what)
