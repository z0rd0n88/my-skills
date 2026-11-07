---
name: vercel-computer-use
description: 'Operate Linux desktop GUI apps via accessibility trees with the `agent-desktop` CLI: snapshot, click or type by ref, menus, dialogs, windows. Use for an app window no CLI or API reaches.'
---

# vercel-computer-use

`agent-desktop` (npm, Vercel Labs) reads a desktop app's accessibility tree and acts on it. Every command prints one JSON envelope (`ok` plus `data`, or `error`) and exits. It is a tool, not an agent: you run the observe, act, verify loop. It sees only what an app exposes to accessibility; no pixel matching.

Reach for it last. A shell command, file edit, HTTP call, or app CLI beats GUI control whenever one can finish the task. Web pages go to `vercel-agent-browser`.

## Before the first command

1. `agent-desktop status`. Expect `accessibility: granted` and a non-empty `supported_surfaces`. An empty list means the AT-SPI bus did not answer, not an empty desktop. The first call after idle can return `TIMEOUT` while the bus wakes; retry once.
2. Load the guides that ship with the installed version: `agent-desktop skills get desktop`, then `agent-desktop skills get platform`. Flags: `agent-desktop <command> --help`.

## The loop

```bash
agent-desktop list-apps                                           # --app takes the name printed here
agent-desktop snapshot --app gnome-calculator --skeleton -i --compact   # 1. map (small app: plain snapshot -i)
agent-desktop snapshot --root @s2txcl95:e1 -i --compact           # 2. drill into one region
agent-desktop click @s2txcl95:e11                                 # 3. act on a ref
agent-desktop wait --element @s2txcl95:e6 --predicate value --value 7   # 4. verify by reading
```

The step is done when a fresh read shows the expected state. `ok: true` on an action proves delivery, not the outcome.

## Rules

- **Refs are qualified** (`@<snapshot_id>:e<N>`) and valid for one snapshot. Pass them exactly as printed. After any UI change, re-drill that region or snapshot again.
- **Retry only on `disposition.retry: safe`** (delivery `not_delivered`). Any other delivery means the action may have landed: a repeat can click twice, and `toggle` undoes itself. Read live state (`get`, `is`, snapshot) and decide from that.
- **Branch on `error.code`:** `STALE_REF` or `SNAPSHOT_NOT_FOUND` → snapshot again. `AMBIGUOUS_TARGET` → identical twins in the window; on Linux they have no ref path, so act on a unique control. `TIMEOUT` with `resolution_identity_unknown` → nothing sent, retry.
- **Overlays:** when an action lists a menu, sheet, or alert in `data.surfaces`, snapshot that surface next (`snapshot --surface menu --app <name> -i`). Never `--skeleton` a surface.
- **Waits:** `wait --window`, `--element`, `--text`, `--menu`. A fixed sleep is a race. A window appears before its content: wait for the window, then the text.
- **Headless by default.** Use `--headed` (physical mouse and keys) only when the user permits taking over the pointer, never to recover from a headless failure.
- Prefer `set-value` for fields; `clear` then `type` when the app needs key events. A headless `press` never fires a menu item; find the item and `click` it.

## On this machine

This is the **Linux** build running in WSL. It drives Linux GUI apps shown through WSLg; it cannot see Windows apps or Windows browser windows (that is the Orca `computer-use` skill, `orca computer`). WSLg serves Wayland plus XWayland: pointer gestures (`hover`, `drag`, `double-click`, `scroll`) and most window moves need an X11 window and `--headed`; on a Wayland window they refuse. The platform guide's capability table says which command needs what.

## Reference

[reference.md](reference.md): the command map by group, the error and disposition table, Linux gotchas, and the Chromium/Electron handoff to agent-browser. Read it when you need a command the loop does not show or an error you have not handled.
