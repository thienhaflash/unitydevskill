#!/usr/bin/env bash
# Print the Unity Skills REST port whose Editor has THIS project open (matched by projectPath, never by project name).
# Usage: find-editor.sh [unity project folder]      default: UNITY_PROJECT_PATH, else .unity-project / cwd as unity-cli.sh resolves it
# Exit 0 and print the port, or exit 1 listing every Editor that answered.
set -u
want="${1:-${UNITY_PROJECT_PATH:-}}"
if [[ -z "$want" ]]; then
  d="$PWD"
  while [[ "$d" != "/" ]]; do
    if [[ -f "$d/.unity-project" ]]; then rel="$(tr -d '[:space:]' < "$d/.unity-project")"; [[ "$rel" = /* ]] && want="$rel" || want="$d/$rel"; break; fi
    if [[ -d "$d/Assets" && -d "$d/ProjectSettings" ]]; then want="$d"; break; fi
    d="$(dirname "$d")"
  done
fi
[[ -n "$want" ]] || { echo "no project path: pass it, set UNITY_PROJECT_PATH, or run inside the project" >&2; exit 1; }
want="$(cd "$want" 2>/dev/null && pwd -P)" || { echo "project folder not found" >&2; exit 1; }
seen=""
for port in 8090 8091 8092 8093 8094 8095 8096 8097 8098 8099; do
  out="$(curl -s -m 3 -X POST "localhost:$port/skill/project_get_info" -H 'Content-Type: application/json' -d '{}')" || continue
  [[ -n "$out" ]] || continue
  pp="$(printf '%s' "$out" | python3 -c 'import sys,json
try:
  d=json.load(sys.stdin); print(d.get("projectPath") or d.get("result",{}).get("projectPath",""))
except Exception: print("")')"
  [[ -n "$pp" ]] || continue
  pp="${pp%/Assets}"
  rp="$(cd "$pp" 2>/dev/null && pwd -P || echo "$pp")"
  seen="$seen\n  $port  $rp"
  if [[ "$rp" == "$want" ]]; then echo "$port"; exit 0; fi
done
echo "no Editor with $want open on ports 8090-8099. Answered:$seen" >&2
exit 1
