#!/usr/bin/env bash
# Agent-friendly Unity CLI wrapper for Unity Pipeline.
#
# Usage:
#   bash scripts/unity-cli.sh status
#   bash scripts/unity-cli.sh cmd editor_status
#   bash scripts/unity-cli.sh cmd find_gameobjects --name MainCamera
#   bash scripts/unity-cli.sh compile-wait
#   bash scripts/unity-cli.sh console error 20
#   bash scripts/unity-cli.sh menu "Tools/Some Menu Item"
#
# Project resolution (first match wins):
#   1. UNITY_PROJECT_PATH env var
#   2. .unity-project file in cwd or any parent (relative paths resolve from that file's dir)
#   3. cwd if it contains Assets/ + ProjectSettings/
#   4. First child dir under cwd with Assets/ + ProjectSettings/ (monorepo)

set -euo pipefail

source_unity_env() {
  if [[ -f "${HOME}/.unity/env" ]]; then
    # shellcheck disable=SC1091
    source "${HOME}/.unity/env"
  fi
  if ! command -v unity >/dev/null 2>&1; then
    echo "ERROR: unity CLI not found. Install Unity CLI, then run: unity auth login" >&2
    echo "Docs: https://docs.unity.com/en-us/unity-production-pipeline/local-tools-cli/unity-pipeline-package" >&2
    exit 1
  fi
}

resolve_project_path() {
  if [[ -n "${UNITY_PROJECT_PATH:-}" ]]; then
    echo "${UNITY_PROJECT_PATH}"
    return 0
  fi

  local dir="${PWD}"
  while [[ "${dir}" != "/" ]]; do
    if [[ -f "${dir}/.unity-project" ]]; then
      local rel
      rel="$(tr -d '[:space:]' < "${dir}/.unity-project")"
      if [[ -z "${rel}" ]]; then
        echo "ERROR: ${dir}/.unity-project is empty" >&2
        exit 1
      fi
      if [[ "${rel}" != /* ]]; then
        rel="${dir}/${rel}"
      fi
      echo "${rel}"
      return 0
    fi
    dir="$(dirname "${dir}")"
  done

  if [[ -d "${PWD}/Assets" && -d "${PWD}/ProjectSettings" ]]; then
    echo "${PWD}"
    return 0
  fi

  # Monorepo: first child directory that looks like a Unity project
  for child in "${PWD}"/*/; do
    if [[ -d "${child}Assets" && -d "${child}ProjectSettings" ]]; then
      echo "${child%/}"
      return 0
    fi
  done

  echo "ERROR: Unity project not found." >&2
  echo "Set UNITY_PROJECT_PATH, create .unity-project, or cd into the Unity project folder." >&2
  exit 1
}

run_pipeline() {
  local project="$1"
  shift
  unity command --project-path "${project}" --format json --no-banner "$@"
}

wait_for_editor() {
  local project="$1"
  local timeout="${2:-120}"
  local elapsed=0
  while (( elapsed < timeout )); do
    if run_pipeline "${project}" editor_status 2>/dev/null | grep -Eq '"status"[[:space:]]*:[[:space:]]*"ready"'; then
      return 0
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done
  echo "ERROR: Editor not ready after ${timeout}s" >&2
  return 1
}

pipeline_unreachable() {
  local json="$1"
  echo "${json}" | grep -q 'No Pipeline instance found'
}

recompile_status_ok() {
  local json="$1"
  echo "${json}" | grep -qE 'up_to_date|completed' \
    && ! echo "${json}" | grep -qE '"failed"[[:space:]]*:[[:space:]]*true|failed\\":true|"compilationFailed"[[:space:]]*:[[:space:]]*true|compilationFailed\\":true'
}

console_compile_ok() {
  local project="$1"
  local status_json
  status_json="$(run_pipeline "${project}" recompile_status 2>/dev/null || true)"
  if pipeline_unreachable "${status_json}"; then
    return 1
  fi
  recompile_status_ok "${status_json}"
}

compile_wait() {
  local project="$1"
  run_pipeline "${project}" recompile >/dev/null || true
  local elapsed=0
  local timeout=180
  local saw_active=0
  local status_json=""
  while (( elapsed < timeout )); do
    status_json="$(run_pipeline "${project}" recompile_status 2>/dev/null || true)"
    if pipeline_unreachable "${status_json}"; then
      echo "${status_json}" >&2
      echo "ERROR: Pipeline not connected to this project — compile-wait cannot see Editor state." >&2
      echo "Open the project in Unity with com.unity.pipeline installed, or verify compile in the Console." >&2
      return 1
    fi
    if echo "${status_json}" | grep -qE 'triggered|compiling'; then
      saw_active=1
    fi
    if recompile_status_ok "${status_json}"; then
      if (( saw_active == 1 )) || (( elapsed >= 2 )); then
        wait_for_editor "${project}" 60 || true
        echo "${status_json}"
        return 0
      fi
    fi
    # Editor already compiled (e.g. before recompile_status reported a phase)
    if (( elapsed >= 4 )) && console_compile_ok "${project}"; then
      status_json="$(run_pipeline "${project}" recompile_status 2>/dev/null || true)"
      echo "${status_json}"
      return 0
    fi
    sleep 2
    elapsed=$((elapsed + 2))
  done
  echo "ERROR: Compile did not finish within ${timeout}s (recompile_status never reached completed/up_to_date)." >&2
  echo "If Unity already compiled, check Console or run: unity command --project-path \"${project}\" console_status" >&2
  return 1
}

usage() {
  cat <<'EOF'
unity-cli.sh — Unity Pipeline wrapper for agents

Usage:
  unity-cli.sh status                     Editor status (JSON)
  unity-cli.sh pipeline                   Pipeline connection info
  unity-cli.sh console [severity] [limit] Console logs (default: error 50)
  unity-cli.sh compile-wait               Recompile and wait until done
  unity-cli.sh play | stop | pause        Play mode control
  unity-cli.sh hierarchy [limit]          Scene hierarchy (default limit 50)
  unity-cli.sh find --name <name>         Find GameObjects
  unity-cli.sh menu <menu-path>           Execute Editor menu item
  unity-cli.sh read <asset-path>          Read text asset via Editor
  unity-cli.sh cmd <pipeline-cmd> [args]  Run any Pipeline command

Environment:
  UNITY_PROJECT_PATH   Absolute path to Unity project folder
EOF
}

main() {
  source_unity_env
  local project
  project="$(resolve_project_path)"

  local action="${1:-status}"
  shift || true

  case "${action}" in
    -h|--help|help)
      usage
      ;;
    status|ping)
      run_pipeline "${project}" editor_status
      ;;
    pipeline)
      (cd "${project}" && unity pipeline list)
      ;;
    console)
      local severity="${1:-error}"
      local limit="${2:-50}"
      run_pipeline "${project}" console --level "${severity}" --tail "${limit}"
      ;;
    compile-wait)
      compile_wait "${project}"
      ;;
    play)
      run_pipeline "${project}" editor_play
      ;;
    stop)
      run_pipeline "${project}" editor_stop
      ;;
    pause)
      run_pipeline "${project}" editor_pause
      ;;
    hierarchy)
      local limit="${1:-50}"
      run_pipeline "${project}" get_scene_hierarchy --limit "${limit}"
      ;;
    find)
      run_pipeline "${project}" find_gameobjects "$@"
      ;;
    menu)
      local path="${1:?menu path required}"
      run_pipeline "${project}" menu --path "${path}"
      ;;
    read)
      local path="${1:?asset path required}"
      run_pipeline "${project}" read_text_file --path "${path}"
      ;;
    cmd)
      if [[ $# -lt 1 ]]; then
        run_pipeline "${project}"
      else
        run_pipeline "${project}" "$@"
      fi
      ;;
    *)
      echo "ERROR: Unknown action '${action}'" >&2
      usage >&2
      exit 1
      ;;
  esac
}

main "$@"
