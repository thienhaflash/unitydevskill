#!/bin/bash
# usage: [GAME=<id>] build-install.sh [build-id]
# Compile-checks every changed .cs, builds the game's development APK (the profile's menus.buildAndroid) on THIS project's Editor (Unity Skills, projectPath verified), installs it on the
# connected phone and writes out/build-info.json (commit, dirty flag, build time, apk hash) so every later measurement names the build it came from.
# A build takes about 1 to 4 minutes. Never kills or focuses the Editor.
source "$(dirname "$0")/env.sh"
BUILD_ID="${1:-$(git -C "$ROOT" rev-parse --short HEAD)}"
find_skills_port || exit 2
MENU_OPEN="$(pf menus.openScene)"; MENU_BUILD="$(pf menus.buildAndroid)"; RESULT="$PROJECT/$(pf buildResultFile)"
wait_editor || exit 2

post asset_refresh 60 '{}' > /dev/null
sleep 12
wait_editor || exit 2
fail=0
cd "$ROOT" || exit 2
for f in $(git status --porcelain | grep -E '\.cs$' | sed -E 's/^.. //; s/^"//; s/"$//' | grep -v ' '); do
  case "$f" in "$(pf project)"/*) p="${f#$(pf project)/}";; *) continue;; esac
  res=$(post script_get_compile_feedback 30 "{\"scriptPath\":\"$p\"}")
  echo "$res" | grep -q '"hasErrors":false' || { echo "COMPILE ERROR in $p"; echo "$res" | cut -c1-500; fail=1; }
done
[ $fail -eq 0 ] || { echo "ABORT: compile errors"; exit 1; }

post editor_execute_menu 60 "{\"menuPath\":\"$MENU_OPEN\"}" > /dev/null
mkdir -p "$(dirname "$RESULT")"
echo building > "$RESULT"
( post editor_execute_menu 900 "{\"menuPath\":\"$MENU_BUILD\"}" > "$OUT/build-menu.txt" 2>&1 & )
sleep 8
for i in $(seq 1 120); do
  head -1 "$RESULT" | grep -q '^building' || break
  sleep 6
done
head -2 "$RESULT" | cut -c1-200
head -1 "$RESULT" | grep -q '^Succeeded' || { echo "ABORT: build did not succeed"; exit 1; }

APK=$(grep -o '[^ ]*\.apk' "$RESULT" | head -1)
[ -f "$APK" ] || { echo "ABORT: no .apk path in $RESULT"; exit 1; }
"$ADB" install -r -t "$APK" 2>&1 | tail -1

# provenance: which source this APK really is. dirty = uncommitted C#, shader, scene or prefab changes under the project
DIRTY=$(git status --porcelain -- "$PROJECT" | grep -E '\.(cs|shader|cginc|unity|prefab|mat|asset)$' | grep -v 'ProjectSettings' | wc -l | tr -d ' ')
python3 - "$OUT/build-info.json" "$BUILD_ID" "$(git rev-parse HEAD)" "$DIRTY" "$APK" "$GAME" <<'E'
import json, sys, time, hashlib
out, bid, sha, dirty, apk, game = sys.argv[1:7]
h = hashlib.sha1(open(apk, "rb").read()).hexdigest()[:12] if apk else ""
json.dump({"game": game, "build": bid, "commit": sha, "dirtyFiles": int(dirty), "apk": apk, "apkSha": h, "builtAt": time.strftime("%Y-%m-%dT%H:%M:%S")}, open(out, "w"), indent=1)
print("build-info:", bid, sha[:9], "dirty files:", dirty)
E
