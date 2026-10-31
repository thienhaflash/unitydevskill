# Checks after every result

`scripts/validate.py` runs the machine-checkable ones after each sweep (`sweep.sh` calls it and re-runs missing cells once). Go through the rest by hand before a number goes into the
report or a commit message. Each item names the kind of mistake it comes from; all of them happened in practice.

## Automatic (validate.py: MISSING / INVALID / NOTE)

| Message | Meaning | What to do |
|---|---|---|
| `MISSING grid/ab ...` | a unit, section or switch has no reading (the app left the foreground, crashed, or the run was cut) | sweep.sh re-runs it once. If still missing: `adb devices`, screen on, `<perf dir>/out/<name>.txt` for `<TAG> FAIL`, then run that unit alone |
| `INVALID absurd gpu ms` | a reading like 1.8e10 ms (a toggled keyword broke the timer) | dropped from the report (render.py does it); re-run the unit |
| `INVALID toggle suspect` | the "off" side of an A/B differs from the unit's other off-sides by more than 1 ms: switching the treatment changes the cost itself (an anti-aliasing toggle read 20 ms against a 16.3 ms baseline) | the reading is invalid. Make the treatment's off side equal the untreated state, or measure it as two separate runs |
| `INVALID stress scale` | readings tagged with a scale other than the one serialized in the scene (profile `stressScale`). A "stress off" grid was once not off because the scene had saved the stress value | fix the scene value, rebuild, re-run. Never trust a grid without this check |
| `INVALID APK built from <sha>, HEAD is <sha>` | measuring an older or experimental build | `build-install.sh` again from the source you mean to measure |
| `NOTE ... uncommitted files were in the build` | the numbers belong to the working tree, not a commit | commit first, or say so next to the numbers |
| `NOTE negative cost` | switching it off made the frame slower by 0.5 ms or more: noise | counts as 0 in the chart; do not report it as a result |
| `NOTE ... readings under 57 fps although gpu within 16.7 ms` | GPU time alone does not give 60 (two scenes ran 52 fps at about 16 ms GPU) | a steady 60 needs about 14 ms of GPU time. Look at CPU markers, frame pacing, thermal state |
| `NOTE <define> appears in ...` | the profile's `definesCheck`: whether a scripting define that gates a feature is set | see "Defines" below |

## By hand

1. **Read the screenshots, not only the numbers.** `sweep.sh shots` writes one per unit to `<perf dir>/out/`. Look for black or missing geometry, missing shadows, wrong lighting,
   flat colours. A fast build that looks wrong is not a result (a missing light global once turned a whole renderer feature black).
2. **Quality level and AA.** The DEVICE line shows `quality <level> (details)`. Confirm it is the level you pinned, the shadow settings are the game's policy, and anti-aliasing is what
   the build ships. Do not toggle AA at runtime inside a treatment.
3. **Render scale.** The level's scale times the stress multiplier; the DEVICE line shows the resolution actually used. Say which scale a number was taken at.
4. **One fresh game per unit.** A shared session can end partway and later units render an empty scene. If a unit's sections are missing or the screenshot shows nothing playing, that
   unit's numbers are void.
5. **Heat.** Interleaved A/B cancels drift, a plain grid does not. If two runs of the same cell differ by more than 1 fps, let the phone cool and compare again.
6. **Defines.** Check the real define list of the Android target. Code that must run on every build must not sit inside a define that some builds leave off.
7. **The 33 ms column.** Compare the count of frames over 33 ms before and after, not only the mean fps: a unit can hold 59.5 fps and still stall.
8. **Sum against the whole.** The stacked costs are measured one at a time. Add them up and compare with the profile's `totalSwitch` and with the frame time; a big gap means a hidden
   shared cost (for example a screen-space shadow resolve counted in two groups).
9. **Provenance.** The report header names the build and commit of every chart. If you cannot name the build of a number, re-measure it.
10. **Release scale remains the product.** A stress scale is a temporary test setting; reset it before release and say which scale a number was taken at.

## After the checks

- Valid and complete: `log_change.py build` / `effect`, update `status.md`, `render.py`, publish (SKILL.md step 9).
- Invalid or incomplete: fix the cause, re-run, never "adjust" a number by hand.
- A result that moves a decision (a lever, a cut, a quality level) goes to the user with the numbers and the screenshots; cutting a visible feature is the user's call.
