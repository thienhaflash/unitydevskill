#!/usr/bin/env bash
# Idempotent repo setup: git-lfs hooks, binary patterns in .gitattributes, fast-forward-only config, LFS content pull.
# Run from anywhere inside the repo (also in a fresh clone or worktree). Does not commit and does not rewrite history.
set -euo pipefail
command -v git-lfs >/dev/null 2>&1 || git lfs version >/dev/null 2>&1 || { echo "ERROR: git-lfs is not installed (brew install git-lfs, or your platform package), then re-run." >&2; exit 1; }
root="$(git rev-parse --show-toplevel)"; cd "$root"
git lfs install --local >/dev/null
git config merge.ff only
git config pull.ff only
exts="png jpg jpeg tga tif tiff psd exr hdr gif bmp wav mp3 ogg aif aiff flac mp4 mov webm fbx obj blend max ma mb dae ttf otf unitypackage dll so a dylib zip 7z rar apk aab bank"
touch .gitattributes
added=""
for e in $exts; do
  if ! grep -qE "^\*\.$e( |	).*filter=lfs" .gitattributes; then
    printf '*.%s filter=lfs diff=lfs merge=lfs -text\n' "$e" >> .gitattributes; added="$added $e"
  fi
done
[[ -n "$added" ]] && echo "added LFS patterns:$added (commit .gitattributes with the first files it affects)" || echo ".gitattributes already complete"
if git remote | grep -q .; then git lfs pull 2>&1 | tail -2 || true; fi
big="$(git ls-files -s | awk '{print $4}' | while read -r f; do [[ -f "$f" ]] && s=$(wc -c <"$f") && [[ $s -gt 5000000 ]] && ! git check-attr filter -- "$f" | grep -q lfs && echo "$f"; done | head -5)"
[[ -n "$big" ]] && echo "WARNING: tracked files over 5 MB not in LFS (history rewrite needed, ask the user):" && echo "$big"
echo "git-lfs ready; merges are fast-forward only."
