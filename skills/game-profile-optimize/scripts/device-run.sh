#!/bin/bash
# usage: [GAME=<id>] device-run.sh <name> [key=value ...]
# Launches the installed APK of the game with intent extras, saves a screenshot at every SHOT marker, collects the <logTag> log lines (the harness protocol, reference/harness-protocol.md) into $OUT/<name>.txt and
# prints them. Extras are the game's own: its harness reads them and its profile's runs.* templates pass them (reference/harness-protocol.md).
# Typical: a pinned quality level, no automatic step-down, seconds per section, the units to run, ab=<switch,..> for an interleaved on/off sweep, shots=1. The run ends on <logTag> DONE or FAIL.
source "$(dirname "$0")/env.sh"
NAME=$1; shift
EXTRAS=""
for kv in "$@"; do EXTRAS="$EXTRAS --es ${kv%%=*} ${kv#*=}"; done
FILE="$OUT/$NAME.txt"
"$ADB" shell am force-stop "$PKG"
"$ADB" logcat -c
"$ADB" shell input keyevent KEYCODE_WAKEUP
"$ADB" shell am start -n "$PKG/com.unity3d.player.UnityPlayerActivity" $EXTRAS >/dev/null 2>&1
( "$ADB" logcat -s Unity:I | grep --line-buffered "$TAG SHOT" | while read -r line; do tag=$(echo "$line" | sed 's/.*SHOT //'); sleep 0.6; "$ADB" exec-out screencap -p > "$OUT/${NAME}_$tag.png"; done ) &
WATCH=$!
for i in $(seq 1 130); do
  sleep 5
  "$ADB" logcat -d -s Unity:I 2>/dev/null | grep "$TAG" | sed "s/^.*$TAG/$TAG/" | grep -v SHOT > "$FILE"
  grep -q "$TAG DONE\|$TAG FAIL" "$FILE" && break
  if ! "$ADB" shell pidof "$PKG" >/dev/null 2>&1 && [ $i -gt 6 ]; then echo "app not running (crashed?)"; break; fi
done
kill $WATCH 2>/dev/null
pkill -f "logcat -s Unity:I" 2>/dev/null
cut -c1-330 "$FILE"
