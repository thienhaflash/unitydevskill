#!/usr/bin/env python3
"""Build the whole report page of one game from the data store. Nothing in the page is typed by hand: every number comes from <perf dir>/runs.ndjson, the
build history from builds.json, the optimization table from effects.json, the closing text from status.md, the device tiers from devices.json, and
every game-specific word and sentence from <perf dir>/profile.json.

usage: render.py --game <id> [--out report.html] [--tier low] [--files-dir <dir>]
  --tier       the reference tier whose readings fill the charts (the device-tier card always shows every tier)
  --files-dir  also copies <perf dir>/shots/*.jpg to <dir>/shots/ so the page and its screenshots can be published together
"""
import argparse, html, json, os, shutil, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gameprofile as P

SKILL = P.SKILL


def js(obj):
    return json.dumps(obj, separators=(",", ":")).replace("</", "<\\/")


def valid_ab(recs):
    """Drop the readings validate.py calls invalid: absurd gpu times, and the A/B whose 'off' side differs by >1 ms from its unit's median."""
    groups = {}
    for r in recs:
        if 0 < r["offGpuMs"] < 200 and 0 < r["onGpuMs"] < 200:
            groups.setdefault((r["build"], r["tier"], r["stress"], r["level"], r["unit"]), []).append(r)
    out = []
    for g in groups.values():
        med = statistics.median(r["offGpuMs"] for r in g) if len(g) >= 3 else None
        out += [r for r in g if med is None or abs(r["offGpuMs"] - med) <= 1.0]
    return out


def latest_by(recs, key):
    d = {}
    for r in recs:  # file order is time order; the last reading of a cell wins
        d[key(r)] = r
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default=os.environ.get("GAME") or "-")  # "-" = the only game of the repo
    ap.add_argument("--out")
    ap.add_argument("--tier", default="low")
    ap.add_argument("--files-dir")
    a = ap.parse_args()
    prof = P.load(a.game)
    data = P.data_dir(a.game)
    out_path = a.out or os.path.join(data, "out", "report.html")
    UNITS = list(prof["units"].values())
    SECTIONS = prof["sections"]
    LEVELS = prof["levels"]
    page = prof["page"]
    runs = [json.loads(l) for l in open(os.path.join(data, "runs.ndjson")) if l.strip()]
    tiers = P.devices(a.game)["tiers"]
    builds = json.load(open(os.path.join(data, "builds.json")))
    effects = json.load(open(os.path.join(data, "effects.json")))
    grids = [r for r in runs if r["kind"] == "grid" and r["tier"] == a.tier]
    abs_ = valid_ab([r for r in runs if r["kind"] == "ab" and r["tier"] == a.tier and r["level"] == prof.get("abLevel", "high")])
    release = prof.get("stressScale", {}).get("release", 1.0)

    # release-scale and stress-scale grids: latest reading of every cell
    def grid_table(stress_pred, with_avg):
        cells = latest_by([g for g in grids if stress_pred(g["stress"])], lambda g: (g["unit"], g["level"], g["section"]))
        table = {}
        for u in UNITS:
            row = {}
            for lv in LEVELS:
                vals = [cells.get((u, lv, s)) for s in SECTIONS]
                if all(vals):
                    row[lv] = [[v["fps"], v["over33"]] + ([v["avgMs"]] if with_avg else []) for v in vals]
            if len(row) == len(LEVELS):
                table[u] = row
        return table, list(cells.values())

    final, final_cells = grid_table(lambda s: s <= release, False)
    stress, stress_cells = grid_table(lambda s: s > release, True)

    # cost per group from the profile's costGroups: latest valid reading of the group's switch, negative = noise = 0; "minus" groups are what is left of an overlapping switch
    stress_val = max((r["stress"] for r in abs_), default=release)
    cur = latest_by([r for r in abs_ if r["stress"] == stress_val], lambda r: (r["unit"], r["switch"]))
    featcost = {}
    for u in UNITS:
        if not any((u, cg["switch"]) in cur for cg in prof["costGroups"]):
            continue
        row = {}
        for cg in prof["costGroups"]:
            r = cur.get((u, cg["switch"]))
            row[cg["name"]] = max(0.0, -r["deltaMs"]) if r else 0.0
        for cg in prof["costGroups"]:
            if cg.get("minus"):
                row[cg["name"]] = max(0.0, row[cg["name"]] - sum(row[n] for n in cg["minus"]))
        featcost[u] = {k: round(v, 1) for k, v in row.items()}

    # build history: legacy numbers where there are no raw readings, else Normal/Climax at Medium from the build's own grid
    def build_d(b):
        if b.get("legacyFps"):
            return [b["legacyFps"][u] for u in UNITS]
        cells = latest_by([g for g in grids if g["build"] == b["id"] and g["level"] == "medium"], lambda g: (g["unit"], g["section"]))
        if all((u, s) in cells for u in UNITS for s in ("Normal", "Climax")):
            return [[cells[(u, "Normal")]["fps"], cells[(u, "Climax")]["fps"]] for u in UNITS]
        return None
    builds_js = []
    for b in builds:
        tag = " ".join(x for x in [b.get("commit") and f"commit {b['commit']}", b.get("date")] if x)
        builds_js.append({"id": b["id"], "desc": b["desc"] + (f" ({tag})" if tag else ""), "d": build_d(b)})
    eff_js = [[e["change"], e["kind"], e["effect"], e["result"]] for e in effects]

    # provenance: which build every chart was measured on
    def prov(label, cells):
        if not cells:
            return f"<b>{label}</b>: not measured"
        bs = sorted({(c["build"], c.get("commit")) for c in cells}, key=lambda x: str(x))
        devs = sorted({c["device"].get("model", "?") for c in cells})
        return f"<b>{label}</b>: " + "; ".join(html.escape(str(b)) + (f" ({c[:9]})" if c else "") for b, c in bs) + f" on {html.escape(', '.join(devs))}"
    prov_html = " &middot; ".join([prov("Release-scale grid", final_cells), prov("Stress grid", stress_cells),
                                   prov("Cost breakdown", [r for r in abs_ if r["stress"] == stress_val])])
    meas = [r for r in runs if r["tier"] == a.tier and r["device"]]
    eyebrow = html.escape(" · ".join([prof["name"]] + ([f'{meas[-1]["device"].get("maker", "").capitalize()} {meas[-1]["device"]["model"]}', meas[-1]["device"].get("gpu", ""),
                                                      f'{meas[-1]["device"].get("hz", "")} Hz'] if meas else [])))

    # device tiers: worst fps and slow frames per level, from the latest reading of each cell
    scales = sorted({g["stress"] for g in runs if g["kind"] == "grid"})
    head = "".join(f'<th colspan="{len(LEVELS)}">{"Release scales" if s <= release else f"Stress x{s}"}</th>' for s in scales)
    sub = "".join("".join(f"<th>{lv.capitalize()}</th>" for lv in LEVELS) for _ in scales)
    rows = ""
    for t in tiers:
        tr = [r for r in runs if r["kind"] == "grid" and r["tier"] == t["id"]]
        models = sorted({r["device"].get("model", "?") for r in tr})
        cells = ""
        for s in scales:
            for lv in LEVELS:
                c = latest_by([r for r in tr if r["stress"] == s and r["level"] == lv], lambda r: (r["unit"], r["section"]))
                if len(c) < len(UNITS) * len(SECTIONS):
                    cells += '<td class="off">not measured</td>' if not c else f'<td class="off">partial ({len(c)} cells)</td>'
                    continue
                worst = min(v["fps"] for v in c.values())
                slow = sum(v["over33"] for v in c.values())
                col = "var(--good)" if worst >= 59 else "var(--warn)" if worst >= 55 else "var(--bad)"
                cells += f'<td><b style="color:{col}">{worst:.1f}</b> fps<br><small>{slow} slow frames</small></td>'
        label = f'{html.escape(t["label"])}<br><small>{html.escape(", ".join(models) if models else t["hint"])}</small>'
        rows += f"<tr><td>{label}</td>{cells}</tr>"
    devmatrix = f'<div class="tw"><table><thead><tr><th rowspan="2">Tier</th>{head}</tr><tr>{sub}</tr></thead><tbody>{rows}</tbody></table></div>'

    # closing text: paragraphs, then "- " bullets
    status, bullets = "", []
    for line in open(os.path.join(data, "status.md")).read().splitlines():
        if line.startswith("- "):
            bullets.append(f"<li>{html.escape(line[2:])}</li>")
        elif line.strip():
            status += f'<p class="sub">{html.escape(line.strip())}</p>'
    if bullets:
        status += '<ul style="margin:10px 0 0;padding-left:20px;display:flex;flex-direction:column;gap:6px">' + "".join(bullets) + "</ul>"

    shots = {u: f"shots/{u.lower()}.jpg" for u in UNITS}
    sec_labels = [prof.get("sectionLabels", {}).get(s, s) for s in SECTIONS]
    unit = prof.get("unitLabel", "unit")
    t = open(os.path.join(SKILL, "templates/report.html.tpl")).read()
    # longer tokens first: __UNITS__ (js array) and __UNITS_PL__ (plural word) must not eat __UNIT__
    for k, v in [("__UNITS_PL__", unit + "s"), ("__UNITS__", js(UNITS)), ("__UNIT__", unit),
                 ("__BUILDS__", js(builds_js)), ("__EFF__", js(eff_js)), ("__FINAL__", js(final)), ("__FEATCOST__", js(featcost)), ("__STRESS__", js(stress)),
                 ("__PROV__", prov_html), ("__DEVMATRIX__", devmatrix), ("__STATUS__", status), ("__EYEBROW__", eyebrow),
                 ("__TITLE__", html.escape(page["title"])), ("__FPSINTRO__", html.escape(page["fpsIntro"])), ("__STRESSLABEL__", page["stressLabel"]),
                 ("__SHOTSINTRO__", html.escape(page["shotsIntro"])), ("__COSTINTRO__", html.escape(page["costIntro"])),
                 ("__SECTIONLABELS__", js(sec_labels)), ("__LEVELS__", js(LEVELS)), ("__STRESSTAG__", js(page["stressTag"])),
                 ("__SCALESTRESS__", js(page["scaleStressNote"])), ("__SCALEREL__", js(page["scaleReleaseNote"])), ("__SHOTS__", js(shots)),
                 ("__SHOTALT__", js(page["shotAlt"])), ("__SHOTCAP__", js(page["shotCaption"])), ("__COSTNOTE__", js(page["costNote"]))]:
        t = t.replace(k, v)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    open(out_path, "w").write(t)
    if a.files_dir:
        os.makedirs(os.path.join(a.files_dir, "shots"), exist_ok=True)
        for f in os.listdir(os.path.join(data, "shots")):
            shutil.copy(os.path.join(data, "shots", f), os.path.join(a.files_dir, "shots", f))
    print(f"render: {out_path}  ({len(final)} {unit}s release-scale, {len(stress)} stress, {len(featcost)} cost, {len(builds_js)} builds)")


if __name__ == "__main__":
    main()
