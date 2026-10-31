#!/usr/bin/env bash
# Make sure an Editor with THIS project open is running and answering. Opens one only if none is, and only below the Editor cap.
# Usage: ensure-editor.sh [project folder]     env: MAX_EDITORS (default 5), READY_TIMEOUT seconds (default 120), UNITY_BIN (override the Editor binary)
# Prints "<port>" (Skills REST) on success. Exit codes: 0 ready, 2 cap reached (nothing opened), 3 not responding within the timeout (NOT killed), 4 cannot launch.
# Never kills or focuses an Editor. A new Editor is launched in the background and may show a Safe Mode / compile-error dialog: see reference/editor-lifecycle.md.
set -u
here="$(cd "$(dirname "$0")" && pwd)"
proj="${1:-${UNITY_PROJECT_PATH:-$PWD}}"
while [[ ! -d "$proj/Assets" && "$proj" != "/" ]]; do proj="$(dirname "$proj")"; done
[[ -d "$proj/Assets" ]] || { echo "no Unity project found" >&2; exit 4; }
proj="$(cd "$proj" && pwd -P)"
MAX="${MAX_EDITORS:-5}"; TIMEOUT="${READY_TIMEOUT:-120}"

if port="$("$here/find-editor.sh" "$proj" 2>/dev/null)"; then echo "$port"; exit 0; fi

running="$(pgrep -fl 'Unity.app/Contents/MacOS/Unity( |$)' 2>/dev/null | grep -vci -- '-batchmode' || true)"   # -i: AssetImportWorker children run with -batchMode
if [[ "${running:-0}" -ge "$MAX" ]]; then
  echo "cap: $running Editors already open (max $MAX). Not opening another. Close one you opened yourself (ask the user), or reuse an existing one." >&2; exit 2
fi
# project open but REST not answering yet? then wait, do not launch a second copy (Unity refuses a project that is already open)
if [[ -f "$proj/Temp/UnityLockfile" ]] && pgrep -f "projectPath $proj|-projectpath $proj" >/dev/null 2>&1; then
  echo "project already open, waiting for it to answer" >&2
else
  # LFS pointers instead of binaries make the first import fail and drop into Safe Mode
  git -C "$proj" lfs pull >&2 || echo "git lfs pull failed: install git-lfs (brew install git-lfs && git lfs install); binaries may still be pointers" >&2
  ver="$(sed -n 's/^m_EditorVersion: *//p' "$proj/ProjectSettings/ProjectVersion.txt" | head -1)"
  bin="${UNITY_BIN:-/Applications/Unity/Hub/Editor/$ver/Unity.app/Contents/MacOS/Unity}"
  [[ -x "$bin" ]] || { echo "Editor $ver not found at $bin (set UNITY_BIN)" >&2; exit 4; }
  nohup "$bin" -projectPath "$proj" >/dev/null 2>&1 &
  echo "launched Editor $ver for $proj (pid $!)" >&2
fi
end=$((SECONDS+TIMEOUT))
enabled=0
while (( SECONDS < end )); do
  if port="$("$here/find-editor.sh" "$proj" 2>/dev/null)"; then echo "$port"; exit 0; fi
  # A new project has Unity Skills' "Start On Editor Launch" off, so no REST port ever appears. Reach the Editor over Pipeline and switch the server on (once).
  if (( ! enabled )) && UNITY_PROJECT_PATH="$proj" bash "$here/unity-cli.sh" status 2>/dev/null | grep -Eq '"status"[[:space:]]*:[[:space:]]*"ready"'; then
    UNITY_PROJECT_PATH="$proj" bash "$here/unity-cli.sh" cmd eval 'UnitySkills.SkillsHttpServer.AutoStart = true; UnitySkills.SkillsHttpServer.StartOnEditorLaunch = true; if (!UnitySkills.SkillsHttpServer.IsRunning) UnitySkills.SkillsHttpServer.Start(); return "skills enabled";' >&2 2>&1 && enabled=1
  fi
  sleep 5
done
echo "Editor for $proj did not answer within ${TIMEOUT}s: treat as hung or blocked by a dialog. Not killed. Report to the user." >&2
exit 3
