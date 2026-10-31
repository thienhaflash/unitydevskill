#!/usr/bin/env python3
"""Append the readings of one raw device-run log to <perf dir>/runs.ndjson.

usage: record.py --game <id> <raw-log> --kind grid|ab --build <id> [--level medium] [--stress 1.3]

The line protocol is the one in reference/harness-protocol.md (the profile's logTag in front):
grid  "<TAG> <unit-id> <Section>: frames N fps X avg Y p50 .. | drops>20ms D >33ms E"
ab    "<TAG> AB-RESULT <unit-id> <switch>: off gpu 16.4 ms fps 51.8 | ON gpu 13.7 ms fps 59.2 | delta -2.8 ms"
dev   "<TAG> DEVICE <maker> <model> | <gpu> | <w>x<h> @<hz>Hz | quality <level> (...) | ... | cpu <cpu> | ram <MB> MB"
The build id, commit and dirty flag come from <perf dir>/out/build-info.json (written by build-install.sh); the device from the log's DEVICE line.
"""
import argparse, json, os, re, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gameprofile as P

SKILL = P.SKILL


def parse_device(lines, tag):
    for l in lines:
        m = re.search(tag + r" DEVICE (\S+) ([^|]+)\| ([^|]+)\| (\d+x\d+) @(\d+)Hz \| quality (\w+)[^|]*\|.*?cpu ([^|]+)\| ram (\d+)", l)
        if m:
            return {"model": m.group(2).strip(), "maker": m.group(1), "gpu": m.group(3).strip(), "res": m.group(4), "hz": int(m.group(5)),
                    "cpu": m.group(7).strip(), "ramMb": int(m.group(8))}
    return {}


def tier_of(device, tiers):
    for t in tiers["tiers"]:
        if device.get("model") in t.get("models", []):
            return t["id"]
    return "unclassified"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=os.environ.get("GAME") or "-")  # "-" = the only game of the repo
    ap.add_argument("log")
    ap.add_argument("--kind", required=True, choices=["grid", "ab"])
    ap.add_argument("--build")
    ap.add_argument("--level")
    ap.add_argument("--stress", type=float, default=1.0)
    a = ap.parse_args()

    prof = P.load(a.game)
    data = P.data_dir(a.game)
    out = os.path.join(data, "out")
    tag = prof["logTag"]
    units = prof["units"]
    tiers = P.devices(a.game)
    info = {}
    try:
        info = json.load(open(os.path.join(out, "build-info.json")))
    except OSError:
        pass
    lines = open(a.log).read().splitlines()
    device = parse_device(lines, tag)
    base = {"game": prof["id"], "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "build": a.build or info.get("build"), "commit": info.get("commit"),
            "dirtyFiles": info.get("dirtyFiles"), "apkSha": info.get("apkSha"), "device": device, "tier": tier_of(device, tiers),
            "stress": a.stress, "kind": a.kind}
    sections = "|".join(re.escape(s) for s in prof["sections"])
    recs = []
    for l in lines:
        if a.kind == "grid":
            m = re.search(tag + r" (\S+) (" + sections + r"): frames (\d+) fps ([\d.]+) avg ([\d.]+).*?drops>20ms (\d+) >33ms (\d+)", l)
            if m:
                recs.append({**base, "level": a.level, "unit": units.get(m.group(1), m.group(1)), "unitId": m.group(1), "section": m.group(2),
                             "frames": int(m.group(3)), "fps": float(m.group(4)), "avgMs": float(m.group(5)), "drops20": int(m.group(6)), "over33": int(m.group(7))})
        else:
            m = re.search(tag + r" AB-RESULT (\S+) (\S+): off gpu ([-\d.e+]+) ms fps ([\d.]+) \| ON gpu ([-\d.e+]+) ms fps ([\d.]+) \| delta ([-+\d.e]+) ms", l)
            if m:
                recs.append({**base, "level": a.level, "unit": units.get(m.group(1), m.group(1)), "unitId": m.group(1), "switch": m.group(2),
                             "offGpuMs": float(m.group(3)), "offFps": float(m.group(4)), "onGpuMs": float(m.group(5)), "onFps": float(m.group(6)),
                             "deltaMs": float(m.group(7))})
    if not recs:
        print(f"record.py: no {a.kind} readings in {a.log}", file=sys.stderr)
        sys.exit(1)
    os.makedirs(data, exist_ok=True)
    with open(os.path.join(data, "runs.ndjson"), "a") as f:
        for r in recs:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    print(f"record.py: {len(recs)} {a.kind} readings -> {os.path.join(data, 'runs.ndjson')} ({base['build']}, {device.get('model', 'unknown device')})")


if __name__ == "__main__":
    main()
