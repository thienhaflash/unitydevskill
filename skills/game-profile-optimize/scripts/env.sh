#!/bin/bash
# Sourced by the other scripts. Resolves every path and finds the Editor of THIS project. Nothing here is specific to a game or a machine.
#   GAME          game id = a folder <repo>/.claude/perf/<game>/ holding its profile.json (optional when the repo has exactly one)
#   PERF_DIR      the perf folder itself (default <repo>/.claude/perf/<game>); it holds profile.json, runs.ndjson, builds.json, effects.json, status.md,
#                 devices.json (optional), shots/, history/, out/ (raw logs, git-ignored)
#   UNITY_PROJECT_DIR  Unity project folder (default: the profile's "project" folder in the checkout that holds the cwd; in a worktree that is the worktree's own)
#   ADB           adb command (default: adb on PATH, else $ANDROID_HOME / $ANDROID_SDK_ROOT / the usual SDK folders). "adb -s <serial>" picks one phone.
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GP="python3 $SKILL_DIR/scripts/gameprofile.py"
PERF_DIR="${PERF_DIR:-$($GP "${GAME:--}" --dir)}" || { return 1 2>/dev/null || exit 1; }
export PERF_DIR
GAME="${GAME:-$(basename "$PERF_DIR")}"
pf() { $GP "$GAME" "$@"; }
ROOT="$(git rev-parse --show-toplevel)"
PROJECT="${UNITY_PROJECT_DIR:-$ROOT/$(pf project)}"
DATA="$PERF_DIR"
OUT="$PERF_DIR/out"
if [ -z "$ADB" ]; then
  for c in "$(command -v adb)" "$ANDROID_HOME/platform-tools/adb" "$ANDROID_SDK_ROOT/platform-tools/adb" "$HOME/Library/Android/sdk/platform-tools/adb" "$HOME/Android/Sdk/platform-tools/adb" "$LOCALAPPDATA/Android/Sdk/platform-tools/adb.exe"; do
    [ -n "$c" ] && [ -x "$c" ] && ADB="$c" && break
  done
fi
[ -n "$ADB" ] || { echo "ABORT: adb not found; put it on PATH or set ADB" >&2; return 1 2>/dev/null || exit 1; }
PKG="$(pf package)"
TAG="$(pf logTag)"
mkdir -p "$OUT"

post() { curl -s -m "$2" -X POST "localhost:$SKILLS_PORT/skill/$1" -H 'Content-Type: application/json' -d "$3"; }

# Unity Skills (REST) port whose projectPath is this project. Never the default port, never by project name (every copy is called the same).
# Prints what it probed so a failure can be reported. Sets SKILLS_PORT.
find_skills_port() {
  PROBED=""
  for p in 8090 8091 8092 8093 8094 8095 8096 8097 8098 8099; do
    info=$(curl -s -m 5 -X POST "localhost:$p/skill/project_get_info" -H 'Content-Type: application/json' -d '{}')
    path=$(echo "$info" | grep -o '"projectPath":"[^"]*"' | cut -d'"' -f4)
    [ -z "$path" ] && continue
    PROBED="$PROBED $p=$path"
    case "$path" in "$PROJECT"|"$PROJECT"/*) SKILLS_PORT=$p; return 0;; esac
  done
  echo "ABORT: no Unity Skills port serves $PROJECT. Probed:${PROBED:- nothing answered}. Open that project in an Editor with the Unity Skills plugin, or drive the build another way (see SKILL.md, Editor access)" >&2
  return 1
}

# Wait (bounded) until the Editor answers, i.e. is not compiling or reloading
wait_editor() {
  for i in $(seq 1 20); do
    post console_get_stats 5 '{}' | grep -q '"status":"success"' && return 0
    sleep 3
  done
  echo "Editor still busy after 60 s: report it, do not kill or focus it" >&2
  return 1
}
