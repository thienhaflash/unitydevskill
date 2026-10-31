#!/bin/bash
# usage: [GAME=<id>] sweep.sh grid|ab|shots|all [--units id,id,...] [--levels low,medium,high] [--build-id ID]
#   grid   plain fps grid: every unit  x section at each level, automatic step-down off. Plan about 15 min per level for 8 units.
#   ab     cost breakdown: the profile's switch list interleaved on/off per unit at the profile's abLevel. Plan about 12 min per unit.
#   shots  one gameplay screenshot per unit.
#   all    grid + ab + shots, then validate and render.
# The run arguments (intent extras) come from the profile: runs.grid, runs.ab, runs.shots with {level} {switches} {unit} {units} substituted.
# Runs long: start it with run_in_background and wait for the completion notice, never poll. The APK must already be installed (build-install.sh).
# After every sweep the readings are validated and any unit/level with missing readings is re-run once, automatically.
source "$(dirname "$0")/env.sh" || exit 2
MODE=${1:-all}; shift
UNITS="$(python3 -c "import json;print(','.join(json.load(open('$PERF_DIR/profile.json'))['units']))")"
LEVELS="$(python3 -c "import json;print(','.join(json.load(open('$PERF_DIR/profile.json'))['levels']))")"
BUILD_ID=""
while [ $# -gt 0 ]; do case "$1" in
  --units) UNITS=$2; shift 2;; --levels) LEVELS=$2; shift 2;; --build-id) BUILD_ID=$2; shift 2;; *) echo "unknown arg $1"; exit 2;; esac; done
[ -n "$BUILD_ID" ] || BUILD_ID=$(python3 -c "import json;print(json.load(open('$OUT/build-info.json'))['build'])" 2>/dev/null)
[ -n "$BUILD_ID" ] || { echo "ABORT: no $OUT/build-info.json; run build-install.sh first"; exit 2; }
STRESS=$(python3 "$SKILL_DIR/scripts/stress.py" "$GAME" "$PROJECT")
SWITCHES="$(python3 -c "import json;print(','.join(json.load(open('$PERF_DIR/profile.json'))['switches']))")"
ABLEVEL="$(pf abLevel high)"
REC="python3 $SKILL_DIR/scripts/record.py --game $GAME"
fill() { echo "$1" | sed -e "s/{level}/$2/g" -e "s/{switches}/$3/g" -e "s/{unit}/$4/g" -e "s/{units}/$5/g"; }
echo "sweep $MODE: game $GAME, build $BUILD_ID, stress scale $STRESS, units $UNITS, levels $LEVELS"

run_grid() {  # $1 level
  bash "$SKILL_DIR/scripts/device-run.sh" "grid_$1" $(fill "$(pf runs.grid)" $1 "" "" "") > /dev/null 2>&1
  $REC "$OUT/grid_$1.txt" --kind grid --level $1 --build "$BUILD_ID" --stress $STRESS
}
run_ab() {  # $1 unit id
  bash "$SKILL_DIR/scripts/device-run.sh" "ab_$1" $(fill "$(pf runs.ab)" "" "$SWITCHES" $1 "") > /dev/null 2>&1
  $REC "$OUT/ab_$1.txt" --kind ab --level "$ABLEVEL" --build "$BUILD_ID" --stress $STRESS
}
unit_id() { python3 -c "import json;m=json.load(open('$PERF_DIR/profile.json'))['units'];print([k for k,v in m.items() if v=='$1'][0])"; }

"$ADB" shell input keyevent KEYCODE_WAKEUP
if [ "$MODE" = grid ] || [ "$MODE" = all ]; then for q in ${LEVELS//,/ }; do run_grid $q; done; fi
if [ "$MODE" = ab ] || [ "$MODE" = all ]; then for u in ${UNITS//,/ }; do run_ab $u; done; fi
if [ "$MODE" = shots ] || [ "$MODE" = all ]; then
  bash "$SKILL_DIR/scripts/device-run.sh" shots $(fill "$(pf runs.shots)" "" "" "" "$UNITS") > /dev/null 2>&1
fi

# validate, re-run what is missing once, validate again
for pass in 1 2; do
  python3 "$SKILL_DIR/scripts/validate.py" --game $GAME --build "$BUILD_ID" --project "$PROJECT" > "$OUT/validate.txt"; rc=$?
  head -40 "$OUT/validate.txt"
  [ $rc -ne 3 ] && break
  [ $pass -eq 2 ] && break
  for name in $(grep '^MISSING ab' "$OUT/validate.txt" | awk '{print $(NF-1)}' | sort -u); do echo "re-running ab for $name"; run_ab "$(unit_id $name)"; done
  for q in $(grep '^MISSING grid' "$OUT/validate.txt" | grep -o "'[a-z]*')" | tr -d "')" | sort -u); do echo "re-running grid for $q"; run_grid $q; done
done
python3 "$SKILL_DIR/scripts/render.py" --game $GAME --out "$OUT/report.html" && echo "report: $OUT/report.html (publish it, see SKILL.md)"
exit $rc
