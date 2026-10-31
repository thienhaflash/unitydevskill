# Unity MCP (fallback)

Use only when the CLI and Unity Skills REST both lack the needed operation, or the Editor has no Pipeline and no REST server. It can coexist with the other layers in the same project.

## Setup (check the project's README for the current commands)

CoplayDev's Unity MCP: add the `MCPForUnity` UPM package from its git URL through the Package Manager, start its bridge from the Editor window, and register the MCP server (a `uvx`-launched Python server) in your
agent's MCP configuration. Keep one config per agent, point it at the Editor you mean to drive, and confirm the connection with a read-only tool call before writing. If the project's own rules say not to install it, don't.

## Rules (these prevent recurring mistakes)

1. **Never modify scene prefab instances directly.** Change the prefab asset (`manage_prefabs` modify_contents). If the change is meant to be scene-specific, unpack the prefab first. Direct scene edits create invisible, fragile overrides.
2. **Duplicate before replace.** Read the original (hierarchy, transforms, component properties) before restructuring; compare position, scale, child count and component count after. Never assume defaults; copy the original's values.
3. **Preserve transforms.** Read and keep `localPosition`, `localScale`, `localRotation` (for RectTransform: `anchoredPosition`, `sizeDelta`, `anchorMin`, `anchorMax`, `pivot`).
4. **No duplicate components.** Check `componentTypes` in the hierarchy before adding; after batch operations verify the counts.
5. **Wire every serialized reference.** After adding or replacing components list the serialized fields and wire each one; look for `{fileID: 0}` on required fields. Do not rely on runtime `GetComponent` fallbacks.
6. **Prefab instantiation as a child:** set `localPosition = (0,0,0)` and `localScale = (1,1,1)` explicitly unless the original expects otherwise; MCP can inherit the parent scale.
7. **Scene or prefab?** Reusable element: edit the prefab asset. One-off override: unpack, then edit. Replacing a component on an instance: edit the prefab asset. Adding children to a prefab: `create_child` on the prefab.

After every scene or prefab edit: no duplicate components, no null required references, transforms match the original, child hierarchy as expected, scene saved, compile clean and console clean.
