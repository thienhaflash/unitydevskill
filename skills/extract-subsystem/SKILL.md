---
name: extract-subsystem
description: >-
  Pull a feature out of a Unity game into a portable Assets/{Feature} folder: zero project-deps controller, test driver,
  playable test scene. Use when the user says extract, isolate, standalone, or pull out a feature/prefab/system.
---

# Extract a Unity sub-system

Project- and machine-agnostic. Drive the Editor via `unity-env-setup` preference order (CLI → Skills REST → MCP). Apply `unity-csharp-standards` to new scripts. Compile-verify after every C# or scene write.

## Outcome

- `Assets/{FeatureName}/Scripts/` — one new controller (no project deps) + one test driver
- `Assets/{FeatureName}/Scenes/{FeatureName}TestScene.unity` — playable isolation scene
- Original scripts/prefabs/assets stay put (GUID references); do not copy helper scripts or their `.meta`s

## 1. Ask first

Do not proceed until answered:

1. Feature (name / files / prefabs)
2. Folder name (e.g. `PerfectStreak`)
3. Public API needed (e.g. `OnHit()`, `Reset()`)

## 2. Plan (chat, then save)

Present then save a short plan (update checkboxes as you go):

- Feature summary
- Source assets table (path + GUID): prefab, controller, animators, textures, nested prefabs, SOs
- Prefab hierarchy (names + components)
- Serialized field wiring map
- Dependency strip map (original → replacement)
- Public API signatures
- Steps: controller → driver → scene → wire → compile → play verify

## 3. Discover

1. Assembled prefab (visuals already wired)
2. Main controller (usually the one with managers/singletons)
3. Helper scripts with **no** project deps (leave in place)
4. Related assets (SO, mats, sprites, clips)

Map deps. Strip typical project glue: singletons, event buses, analytics, A/B flags, remote config, project pools, custom coroutine runners (MEC/UniTask → `StartCoroutine` unless keeping the dep is intentional).

## 4. Controller

One new script under `Assets/{FeatureName}/Scripts/`:

- Same behavior; **no** project deps
- Replace with: `[SerializeField]` assets/config, public methods + C# events, local state
- Optional `#if UNITY_EDITOR` shortcuts for manual test
- Namespace: match the project or ask — do not invent one

| Original | Replacement |
|---|---|
| `Singleton.Instance.X()` | Serialize / inject / find once in `Awake` |
| Event bus subscribe/publish | `event Action<…>` or direct call |
| Analytics / A/B / remote config | Drop, or `[SerializeField]` defaults |
| Project pool spawn/recycle | `Instantiate`/`Destroy` or minimal pool |
| External coroutine runner | `StartCoroutine` |

Compile clean before the scene.

## 5. Test driver

`{FeatureName}TestDriver.cs` beside the controller:

- `OnGUI` button per public API method (+ `+10` if there is a streak/counter)
- Resolve controller via serialize or `FindAnyObjectByType`
- Live state label; editor-only keyboard mirrors

## 6. Test scene

1. Create `Assets/{FeatureName}/Scenes/{FeatureName}TestScene.unity`
2. Camera: dark solid clear, sees all layers; position so the feature is visible
3. Instantiate the **assembled** prefab — do not rebuild hierarchy from scratch
4. Strip unrelated children (UI chrome, analytics hooks)
5. On the controller GO: remove original controller component; add the new one
6. Wire every serialized field from the original prefab YAML (scene refs by instance, assets by GUID)
7. Add an empty GO with the test driver; wire controller; save

## 7. Validate & report

1. Compile-verify → zero errors  
2. Enter play → zero runtime errors → screenshot → exercise OnGUI/shortcuts → stop play  
3. Report: folder path, how to drive it, public API, that `Assets/{FeatureName}/` is copyable, any helpers that must still exist elsewhere

## Rules

- Do not rewrite/copy helpers; do not copy script `.meta`s; do not reparent under Canvas unless the feature needs it
- Do not use `PrefabUtility.LoadPrefabContents` to swap scripts at runtime
- Always read original prefab YAML before wiring values
- Never ask the user to wire the scene by hand when Editor automation is available
