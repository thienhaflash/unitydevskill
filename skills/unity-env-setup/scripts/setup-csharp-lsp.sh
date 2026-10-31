#!/usr/bin/env bash
# Install C# code hints (OmniSharp) into VS Code or Cursor so .cs files get go-to-definition and IntelliSense.
# Usage: setup-csharp-lsp.sh [code|cursor]      default: whichever CLI is found (cursor first)
# Run once per machine, then restart the editor. Needs a Unity-generated .sln (see reference/csharp-code-hints.md).
set -euo pipefail
EDITOR_KIND="${1:-}"
find_cli() {
  local kind="$1"
  case "$kind" in
    cursor) for c in /Applications/Cursor.app/Contents/Resources/app/bin/cursor "$HOME/.local/bin/cursor" "$(command -v cursor 2>/dev/null || true)"; do [[ -n "$c" && -x "$c" ]] && { echo "$c"; return; }; done ;;
    code)   for c in "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code" "$(command -v code 2>/dev/null || true)"; do [[ -n "$c" && -x "$c" ]] && { echo "$c"; return; }; done ;;
  esac
}
CLI=""
if [[ -n "$EDITOR_KIND" ]]; then CLI="$(find_cli "$EDITOR_KIND")"; else
  for k in cursor code; do CLI="$(find_cli $k)"; [[ -n "$CLI" ]] && { EDITOR_KIND=$k; break; }; done
fi
[[ -n "$CLI" ]] || { echo "ERROR: neither the Cursor nor the VS Code command line was found (install the 'cursor' / 'code' shell command)." >&2; exit 1; }
case "$EDITOR_KIND" in cursor) EXT_ROOT="$HOME/.cursor/extensions" ;; code) EXT_ROOT="$HOME/.vscode/extensions" ;; esac

echo "-> installing the C# extension with $CLI"
"$CLI" --install-extension muhammad-sammy.csharp
EXT_DIR="$(find "$EXT_ROOT" -maxdepth 1 -type d -name 'muhammad-sammy.csharp-*' 2>/dev/null | sort | tail -1)"
[[ -n "$EXT_DIR" ]] || { echo "ERROR: extension folder not found under $EXT_ROOT after install" >&2; exit 1; }

VER="${OMNISHARP_VERSION:-1.39.14}"
case "$(uname -s)-$(uname -m)" in
  Darwin-arm64)  PLAT=osx-arm64 ;;
  Darwin-x86_64) PLAT=osx-x64 ;;
  Linux-x86_64)  PLAT=linux-x64 ;;
  Linux-aarch64) PLAT=linux-arm64 ;;
  *) echo "ERROR: unsupported platform $(uname -sm) (on Windows install the extension from the Extensions view; it downloads OmniSharp itself)." >&2; exit 1 ;;
esac
DEST="$EXT_DIR/.omnisharp/${VER}-net6.0"
if [[ -f "$DEST/OmniSharp.dll" ]]; then echo "-> OmniSharp already present"; else
  rm -rf "$DEST"; mkdir -p "$DEST"
  TMP="$(mktemp -t omnisharp.XXXXXX).zip"
  curl -fL "https://roslynomnisharp.blob.core.windows.net/releases/${VER}/omnisharp-${PLAT}-net6.0.zip" -o "$TMP"
  unzip -oq "$TMP" -d "$DEST"; rm -f "$TMP"
  echo "-> OmniSharp installed: $DEST"
fi
echo "Done. Restart the editor. In Unity: Edit > Preferences > External Tools > Regenerate project files (needs the .sln)."
