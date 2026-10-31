#!/usr/bin/env python3
"""Check the readings of one build before anyone reads a number out of them.

usage: validate.py --game <id> [--build ID] [--project <Unity project folder>]
Exit 0 = clean (notes allowed), 2 = invalid readings, 3 = readings missing (sweep.sh re-runs the missing cells itself once).
Each check below exists because it bit once; see reference/checks.md for what to do about each message.
"""
import argparse, json, os, statistics, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gameprofile as P


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=os.environ.get("GAME") or "-")  # "-" = the only game of the repo
    ap.add_argument("--build")
    ap.add_argument("--project")
    a = ap.parse_args()
    prof = P.load(a.game)
    DATA = P.data_dir(a.game)
    OUT = os.path.join(DATA, "out")
    themes = sorted(prof["units"].values())  # the units of the game (e.g. themes, tracks, levels)
    SECTIONS = prof["sections"]
    SWITCHES = prof["switches"]
    recs = [json.loads(l) for l in open(os.path.join(DATA, "runs.ndjson")) if l.strip()]
    info = {}
    try:
        info = json.load(open(os.path.join(OUT, "build-info.json")))
    except OSError:
        pass
    build = a.build or info.get("build") or (recs[-1]["build"] if recs else None)
    recs = [r for r in recs if r["build"] == build]
    bad, missing, notes = [], [], []
    print(f"validate: build {build}, {len(recs)} readings")
    if not recs:
        print("INVALID: no readings for this build")
        sys.exit(2)

    # 1. completeness: every unit has every section at every level measured, and every unit has every switch
    grids = {}
    for r in (x for x in recs if x["kind"] == "grid"):
        grids.setdefault((r["tier"], r["stress"], r["level"]), set()).add((r["unit"], r["section"]))
    for key, have in grids.items():
        for t in themes:
            for s in SECTIONS:
                if (t, s) not in have:
                    missing.append(f"grid {key} {t} {s}")
    abs_ = {}
    for r in (x for x in recs if x["kind"] == "ab"):
        abs_.setdefault((r["tier"], r["stress"], r["level"]), {}).setdefault(r["unit"], set()).add(r["switch"])
    for key, per in abs_.items():
        for t in themes:
            for sw in SWITCHES:
                if sw not in per.get(t, set()):
                    missing.append(f"ab {key} {t} {sw}")

    # 2. absurd values (a toggled keyword once returned 1.8e10 ms)
    for r in recs:
        if r["kind"] == "ab" and not (0 < r["offGpuMs"] < 200 and 0 < r["onGpuMs"] < 200):
            bad.append(f"absurd gpu ms: {r['unit']} {r['switch']} off {r['offGpuMs']} on {r['onGpuMs']}")
        if r["kind"] == "grid" and not (0 < r["fps"] <= 130 and 1 < r["avgMs"] < 500):
            bad.append(f"absurd frame stats: {r['unit']} {r['section']} fps {r['fps']} avg {r['avgMs']}")

    # 3. the 'off' side of every A/B must equal the untreated baseline; if one differs the toggle itself changes the cost (MSAA test: 20 ms vs 16.3 ms)
    for key, per in abs_.items():
        for t in themes:
            offs = [(r["switch"], r["offGpuMs"]) for r in recs if r["kind"] == "ab" and (r["tier"], r["stress"], r["level"]) == key and r["unit"] == t and 0 < r["offGpuMs"] < 200]
            if len(offs) >= 3:
                med = statistics.median(v for _, v in offs)
                for sw, v in offs:
                    if abs(v - med) > 1.0:
                        bad.append(f"toggle suspect: {t} {sw} off-side {v:.1f} ms vs the unit's median off-side {med:.1f} ms (>1 ms): the switch itself changes the cost, reading invalid")

    # 4. noise floor and 5. fps against gpu time
    pacing = {}
    for r in recs:
        if r["kind"] == "ab" and r["deltaMs"] > 0.5:
            notes.append(f"negative cost (noise, count as 0): {r['unit']} {r['switch']} +{r['deltaMs']:.1f} ms when switched off")
        if r["kind"] == "ab" and 0 < r["offGpuMs"] <= 16.7 and r["offFps"] < 57:
            pacing.setdefault(r["unit"], []).append(r["offFps"])

    for t, v in sorted(pacing.items()):
        notes.append(f"{t}: {len(v)} readings under 57 fps (lowest {min(v):.1f}) although gpu time was within 16.7 ms. A steady 60 needs about 14 ms of GPU time; look at CPU markers and frame pacing too")
    # 6. scale really applied: the stress scale is serialized in the game's scene (profile stressScale)
    if a.project and info.get("build") == build and prof.get("stressScale"):
        scene = os.path.join(a.project, prof["stressScale"]["file"])
        key = prof["stressScale"]["key"]
        try:
            line = next(l for l in open(scene) if f"{key}:" in l)
            scene_stress = float(line.split(":")[1])
            for st in sorted({r["stress"] for r in recs}):
                if abs(st - scene_stress) > 1e-6:
                    bad.append(f"stress scale: readings are tagged {st} but {os.path.basename(scene)} serializes {scene_stress}; the APK was built with the scene value")
        except (OSError, StopIteration):
            notes.append("could not read the stress scale from the scene")

    # 7. the APK matches the committed source
    if info.get("build") == build:
        head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        if info.get("commit") != head:
            bad.append(f"APK built from {str(info.get('commit'))[:9]}, HEAD is {head[:9]}: measuring an older or experimental build")
        if info.get("dirtyFiles"):
            notes.append(f"{info['dirtyFiles']} uncommitted source/asset files were in the build: the numbers belong to the working tree, not to the commit")

    # 8. scripting defines (a missing scripting define once left a whole renderer feature uninitialised; the profile's definesCheck names the define to look for)
    dc = prof.get("definesCheck")
    if a.project and dc:
        defs = subprocess.run(["grep", "-rl", dc["define"]] + [os.path.join(a.project, p) for p in dc["paths"]], capture_output=True, text=True).stdout.split()
        notes.append(f"{dc['define']} appears in: " + (", ".join(os.path.basename(p) for p in defs) if defs else "no settings file") + " (check the real define list of the Android target)")

    for m in missing[:60]:
        print("MISSING", m)
    if len(missing) > 60:
        print(f"MISSING ... and {len(missing) - 60} more")
    for b in bad:
        print("INVALID", b)
    for n in notes[:40]:
        print("NOTE", n)
    print(f"validate: {len(bad)} invalid, {len(missing)} missing, {len(notes)} notes")
    sys.exit(2 if bad else 3 if missing else 0)


if __name__ == "__main__":
    main()
