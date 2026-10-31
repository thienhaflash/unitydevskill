---
name: git-workflow
description: >-
  Git rules for agents working in any repo, especially Unity projects with worktrees: always set up git-lfs for binary assets, always fast-forward (never create merge commits), and always write and commit a handoff
  note before removing a worktree so the next agent can continue. Use when starting in a repo, creating or removing a worktree, merging, rebasing, committing binary assets, or ending a session.
---

# Git workflow rules

## 1. Always have git-lfs set up, so binaries load properly

At the start of work in a repo (and in every new clone or worktree), run `bash scripts/init-lfs.sh` from the repo root. It is idempotent: it runs `git lfs install --local`, adds missing patterns to `.gitattributes`
(textures, audio, video, models, fonts, archives, compiled libs, Unity binaries such as `.unitypackage`, `.exr`, `.hdr`, `.fbx`, `.psd`, `.wav`, `.mp3`, `.ogg`, `.mp4`, `.dll`, `.so`, `.a`, `.zip`, `.apk`, `.aab`), then runs `git lfs pull`.
- Commit `.gitattributes` together with the first files it affects. Never leave it untracked.
- If `git lfs` is missing, install it (`brew install git-lfs` / the platform package) before continuing; do not work around it by committing big binaries as plain blobs.
- A file shows up as a ~130-byte text pointer instead of the real asset: run `git lfs pull`; the cause is a clone or worktree made without LFS.
- Binaries **already committed** as plain blobs stay in history. Converting them needs `git lfs migrate import`, which **rewrites history**: never run it unasked; propose it to the user with the affected paths and sizes first.
- Unity: keep Asset Serialization on Force Text and Version Control on Visible Meta Files so scenes and prefabs diff and merge as text; only true binaries go to LFS. Always commit the `.meta` files with their assets.

## 2. Always fast-forward; never create a merge commit

- Set once per repo: `git config merge.ff only` and `git config pull.ff only` (the init script does it), or `pull.rebase true` if the user prefers that.
- Integrating a branch: `git fetch origin && git rebase origin/<base>` on the feature branch, resolve conflicts there, then on the base `git merge --ff-only <feature>`. If `--ff-only` refuses, the branch is not rebased: rebase again, never fall back to a plain merge.
- Never run `git merge` without `--ff-only`, never `git pull` that can merge, never use `--no-ff`, never accept a "Merge branch ..." commit from a tool. On a hosted PR use rebase-and-merge or fast-forward, not "Create a merge commit" and not squash unless the user says so.
- Rebasing rewrites only your own unpushed or personal branch commits; never force-push a shared branch. If a push needs `--force`, use `--force-with-lease` on your own branch only and say so.
- In a worktree app that offers a "sync with base" action, use it only if it is fast-forward/rebase; otherwise rebase by hand.

## 3. Handoff before removing a worktree

A worktree's branch outlives the folder. Before `git worktree remove` (or any tool that removes it), write a handoff file **in the repo**, commit it on the branch, and only then remove the worktree. Do not remove a worktree with uncommitted
changes: commit them (work in progress is fine) or tell the user.

1. Copy `templates/HANDOFF.md` to `.claude/handoff/<branch-slug>.md` (slash in the branch name becomes `-`) and fill **every** section from what you actually know: goal and plan, decisions and why, implementation status with the
   commits, what was verified and how, what is not verified, known problems, the exact todo list in order, files to read first, commands to resume (build, run, Editor project path), and traps already hit.
2. `git add .claude/handoff/<branch-slug>.md` and commit: `docs(handoff): <branch> state at <date>`. Include other uncommitted work in separate commits first.
3. Push the branch if a remote is set and the user wants it pushed; otherwise say the handoff is local to this clone.
4. Confirm `git status` is clean and `git log -1` shows the handoff, then remove the worktree.
5. When you **check out a branch** (new worktree or session), look for `.claude/handoff/<branch-slug>.md` first, read it, trust the todo list but verify the status against `git log` and the build, and update the file as you go. When the work
   is merged, delete the handoff file in the final commit of the branch.

The handoff must be enough for an agent with no memory of this session: no "see above", no references to chat history, absolute paths replaced by repo-relative ones.

## Files

- `scripts/init-lfs.sh`: LFS install, `.gitattributes` patterns, ff-only config, `git lfs pull`.
- `templates/HANDOFF.md`: the handoff skeleton.
