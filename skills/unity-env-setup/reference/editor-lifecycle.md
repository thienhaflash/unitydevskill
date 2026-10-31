# Editor lifecycle: open, cap, hang, reconnect, dialogs

## One Editor per checkout/worktree

An agent working in a git worktree needs the Editor of **that worktree's** Unity folder, not the main checkout's. Run `bash scripts/ensure-editor.sh <worktree unity folder>`: it returns the Skills REST port if an Editor with that
exact path already answers, otherwise launches the version in `ProjectSettings/ProjectVersion.txt` in the background (never `-batchmode` for interactive work) and waits for it. A fresh worktree has no `Library/`, so the first
import takes several minutes: that is expected, but the 2-minute rule below still applies to "answers at all" (the REST server starts once the first compile finishes; report progress instead of waiting silently).

## Cap: no more than 5 Editors

`ensure-editor.sh` counts running Editors and refuses to open another at `MAX_EDITORS` (default 5, exit 2). Then: reuse an Editor that already has the project, or ask the user which one to close. Only an Editor **you launched
yourself** may be closed by you, and only through its own quit command (`unity-cli.sh cmd quit` or the REST equivalent), never with kill signals. Close the worktree's Editor when its work is merged and the worktree is removed.

## Hang rule: 2 minutes

If an Editor does not answer (CLI `status`, REST `/health`) for **120 s**, call it hung or blocked by a dialog. Do not keep waiting and do not kill it:
1. `unity-cli.sh cmd recompile`, then re-check once (this fixes "compiling forever" states).
2. Look for a blocking dialog (below). If it is yours (you launched it) and the user allowed computer use, handle it; otherwise report it.
3. Report: which project, which port/PID, what was tried, and that the Editor is not killed. Continue with work that does not need the Editor (reading, editing files) and say what is unverified.
Never loop on the same failing status check; change route (CLI -> REST -> MCP) or report.

## Reconnect Unity Skills / Pipeline after a domain reload or restart

The REST server goes down during a domain reload (2-5 s) and may come back **on a different port** after an Editor restart. After a failed call: wait 3 s, then re-resolve the port with `scripts/find-editor.sh <project>`
(never reuse a cached port blindly), retry up to 5 times, and only then treat it as a hang. Pipeline: `unity-cli.sh status` retries the same way. If the REST toggle is off after a restart: `Window > UnitySkills` and switch the server on
(or `menu` command if the package exposes one). Re-verify `projectPath` after every reconnect.

## Dialogs at startup (Safe Mode, license, upgrade prompts)

There is no command-line flag that skips the "Enter Safe Mode?" dialog; it appears when the project has compile errors at startup. In order:
1. Prevent it: before launching, make sure the code compiles (fix errors first), and that `Library/` is not half-written. A project that compiled when last closed will not show it.
2. If it appears anyway, the Editor will not answer REST/CLI. With computer use available and **the user's permission for this session** (clicking steals window focus, which the user may forbid), screenshot, confirm the window belongs to the project you
   launched (title shows the project folder), and click **Ignore** (continue into the project) rather than "Enter Safe Mode"; then fix the compile errors through the normal loop. Never click on an Editor window you did not launch.
3. Without computer use or permission: report the dialog and stop waiting; do not kill the Editor.
Other prompts (API upgrade "Yes, for these and other files", license/sign-in) are the user's to answer; report them.
