---
name: unity-csharp-standards
description: >-
  Unity C# coding standards for any project: naming, namespaces, control flow, GC/hot-path rules, forbidden Unity APIs,
  events vs Update, null guards, logging, tests. Use when writing or editing .cs, writing unit tests, or reviewing C# style.
---

# Unity C# coding standards

Project- and machine-agnostic. Apply to every `.cs` change. After edits, run the compile-verify loop from `unity-env-setup` (stop play → compile-wait → zero console errors) before saying done.

Project steering / `.cursor/rules/` / existing aliases override conflicting items here — match the repo.

## Naming

| Symbol | Convention | Example |
|---|---|---|
| Type / method / property / public field / const | `PascalCase` | `GetLength()`, `MaxCount` |
| Private field | `_camelCase` | `_wallId` |
| Local | `camelCase` | `targetGo` |
| Event | `On` + `PascalCase` | `OnChanged` |

Prefer short names (`go`, `comp`, `mgr`). One namespace per package; no `.Editor` suffix; no per-feature sub-namespaces.

## Usings

Alias ambiguous Unity types the way **this repo already does** (`UnityObject`, etc.). Prefer `using` + short name over FQNs. Qualify static calls (`RhythmJson.Parse`, not bare `Parse`). `using static` OK for nested types/constants; not for `Math`/`Mathf` utilities.

## Control flow

Early returns; main path flat; max ~2 nesting levels. Extract complex conditions into named bools.

```csharp
if (go == null) return;
if (!_cache.ContainsKey(go)) return;
Execute(data);
```

If formatting: same-line single statement → no braces (`if (x == null) return;`). Multi-line or if/else → braces on both sides.

## GC / hot paths

Ask “does this allocate?” on every hot-path line.

- Cache collections; `Clear()` + non-alloc `GetComponents(list)` — never `new` / LINQ (`.Where`, `.ToList`, `.ToArray`) in Update.
- `Array.Empty<T>()` not `new T[0]`; pre-size lists/dicts; `CompareTag` not `.tag ==`.
- Pool temps (`ObjectPool<List<…>>`); in 10k+ loops prefer `ReferenceEquals` for pure null, else Unity `==`.
- Mesh: `MarkDynamic` once; per frame `SetVertices` / `SetUVs` / `SetIndices` / assign `bounds` — never `mesh.vertices` getter/setter or `RecalculateBounds` in hot paths.
- Materials: never `renderer.material` / `.materials` (duplicates). Use `sharedMaterial` or `MaterialPropertyBlock`.

## Forbidden / restricted Unity APIs

| Avoid | Prefer |
|---|---|
| `FindObject(s)OfType` / `FindObjectsByType` / `GameObject.Find` / `SendMessage` | Serialize, Awake cache, registry |
| `Camera.main` / `GetComponent*` in loops | Cache in Awake |
| `renderer.material(s)`, mesh property setters | shared / MPB / `Set*` APIs |
| `Destroy` + re-`Instantiate` for reuse | `SetActive` + pool/reuse |

Ask before `PlayerPrefs` / `EditorPrefs` (prefer ScriptableObject / config assets).

## Events, Update, destroy

- Subscribe in `Awake`, unsubscribe in `OnDestroy` — not `OnEnable`/`OnDisable` (breaks when disabled).
- No `Update` polling for state changes — use events.
- `OnDestroy`: clear data only; do not fire state-machine / listener callbacks on dying objects.

## Nulls, logs, comments

Justify every null check; no silent `?.` that hides bugs — log with `[ClassName]` and return/throw. No blanket try/catch.

- `Debug.Log` — not in production paths; Warning = recoverable; Error = broken invariant. Prefer one summary log over per-item spam.
- Comments explain *why* only. No XML/`#region`/value-in-comment drift. One type per file; partials instead of regions. Class order: consts → static → serialized → public → private → lifecycle → public methods → private.

## Methods & packages

One job per method; caller owns flow (`TryX` → bool). No drive-by format/refactor/usings. No new cross-package dependency without asking. Delete unused private/internal; `[Obsolete]` only for public API.

Prefer simple fields over trivial properties; `readonly struct` for plain data; `var` only when the type is obvious.

## Unit tests (UTF)

Layout: `Tests/Runtime/` asmdef referencing the runtime assembly + TestRunner; `InternalsVisibleTo` in runtime `AssemblyInfo.cs`.

- Names: `Feature_Scenario_Expected`. AAA. Property-style loops ≥100 iterations where useful.
- TearDown: try/catch cleanup so one failure doesn’t poison the suite. `LogAssert.Expect` for intentional errors. Prefer seeded RNG; no timing flakes.
- Performance: `[Performance]` + `Measure.Method(...).GC().Run()` when measuring alloc/cost.

## Quick checks

| Prefer | Avoid |
|---|---|
| Early returns, ≤2 nest | Deep if pyramids |
| Cached lists / manual loops | LINQ / `new` in Update |
| `Awake`/`OnDestroy` events | `OnEnable` subscribe, Update poll |
| `SetActive` reuse | Destroy/Instantiate churn |
| Explicit null + LogError | Silent `?.` |
| Match repo aliases | Inventing `UObj` vs `UnityObject` |
