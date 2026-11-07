# agent-desktop reference

Condensed from https://agent-browser.dev/desktop and the guides bundled in the binary (v1.2.0): `agent-desktop skills get desktop [<reference>]` and `agent-desktop skills get platform`. The binary's guides match its exact version; prefer them over this file when they disagree. References: `commands-observation`, `commands-interaction`, `commands-system`, `workflows`; the Linux guide adds `bus-and-permissions`, `display-servers-and-input`, `windows-and-lifecycle`, `capture-and-clipboard`, `shell-tray-and-notifications`, `troubleshooting`.

## Output envelope

`{"version":"2.6","ok":true,"command":"...","data":{...}}` or `{"ok":false,"error":{"code","message","suggestion","recovery","details","disposition"}}`. Branch on `error.code` and `disposition`; message text can change. Parse with `jq` or `python3 -c 'import json,sys;...'`.

## Commands by group

| Group | Commands |
|---|---|
| Observe | `snapshot` (`--app`, `--skeleton`, `--root @ref`, `-i`, `--compact`, `--surface window|menu|menubar|sheet|popover|alert`, `--max-depth`), `find` (`--role --name --text --value --exact --root --first`), `get @ref --property text|value|title|bounds|role|states`, `is @ref --property visible|enabled|checked|focused|expanded|selected`, `screenshot`, `list-surfaces` |
| Act on refs | `click`, `right-click`, `type`, `set-value`, `clear`, `focus`, `select`, `toggle`, `check`, `uncheck` (idempotent), `expand`, `collapse`, `scroll-to` |
| Physical input (`--headed`) | `double-click`, `triple-click`, `hover`, `drag`, `scroll`, `mouse-move`, `mouse-click --xy X,Y`, `mouse-wheel`. `key-down`, `key-up`, `mouse-down`, `mouse-up` always fail closed |
| Keyboard | `press <combo>` (`return`, `escape`, `ctrl+c`, `shift+tab`). Blocked combos refuse without `--force` |
| Apps and windows | `launch <app>` (`--activate` waits for a window, `--arg`, `--env`, `--cdp [port]`), `close-app` (`--force`), `list-apps`, `list-windows`, `list-displays`, `focus-window`, `resize-window`, `move-window`, `minimize`, `maximize`, `restore` |
| Clipboard | `clipboard-get`, `clipboard-set`, `clipboard-clear` |
| Notifications | `list-notifications`, `dismiss-notification`, `dismiss-all-notifications`, `notification-action` (GNOME Shell only on Linux) |
| Wait | `wait <ms>`, `--element @ref --predicate value --value X`, `--window "<title>" --app <name>`, `--text`, `--menu`, `--menu-closed`, `--event window-closed`, `--timeout <ms>` |
| System | `status`, `permissions`, `version`, `batch '<json array>' [--stop-on-error]`, `skills list|get|path`, `session start|end|list|gc`, `trace`, `cursor-overlay`, `mcp` (serves every command as an MCP tool over stdio) |

Snapshot and ref actions also take `-w/--wait-for role:text` and `--wait-for-gone role:text` to poll and return the snapshot in one call.

## Snapshot strategy

- Small app: `snapshot --app X -i`.
- Dense app (Electron, more than ~50 controls): `--skeleton -i --compact` shows cut branches with `children_count`; drill one with `--root @ref`. A drill adds refs to the same snapshot id; refs that were inside the re-drilled subtree are replaced (old ones return `STALE_REF`), others stay valid.
- Known control: `find --app X --role button --name "Save" --exact --first` skips the map.
- `-i` drops static-text labels. To tell which row a repeated button belongs to, drill the row container without `-i`.

## Errors and disposition

| Signal | Meaning | Next move |
|---|---|---|
| `disposition.delivery: not_delivered`, `retry: safe` | Nothing reached the app | Retry or substitute |
| Any other delivery | Action may have landed | Read live state before anything else; never blind-repeat |
| `STALE_REF` (`saved_ref_absent`) | Element gone or changed | Fresh snapshot, new ref |
| `AMBIGUOUS_TARGET` (`identity_not_unique`, `saved_ref_ambiguous`) | Twin elements; on Linux the ref was never unique in the window | Target a unique control; re-snapshotting twins refuses again. After a slow window, retake with a larger timeout |
| `TIMEOUT` (`resolution_identity_unknown`) | Live read did not answer; nothing sent | Retry |
| `SNAPSHOT_NOT_FOUND` | Snapshot id expired | Snapshot again |
| `POLICY_DENIED` / `ACTION_NOT_SUPPORTED` | Needs `--headed`, or the display server refuses it | Find a semantic path; ask before going headed |
| `details.retryable: false` | Waiting cannot help | Change approach |

## Linux and WSL gotchas

- Run inside the target app's desktop session (here: WSLg, `DISPLAY=:0`, `WAYLAND_DISPLAY=wayland-0`, session bus at `/run/user/1000/bus`). An SSH shell or container without those variables sees no apps.
- `--app` takes the name `list-apps` prints (`gnome-calculator`, `nautilus`) or a desktop-entry name, never a window title.
- Window ids are opaque and die with the process; run `list-windows` again after a restart.
- GTK4 apps nest deeply; read past nameless `group` nodes. A GTK4 entry with hidden characters is still readable; only password roles are withheld.
- Chromium and Qt apps need a launch flag or variable to appear on the bus; Electron needs only `--no-sandbox` where `chrome-sandbox` is not setuid (see the `troubleshooting` reference).
- `focus-window` needs X11; `focus` needs `--headed` and GTK4 rejects it.
- Screenshots: X11 windows need no permission; Wayland asks for portal consent.
- Clipboard on Wayland needs `wl-clipboard`.
- The state root `~/.agent-desktop` must be private (`chmod 700`), or `snapshot` fails with `INTERNAL`.

## Chromium and Electron apps

For an app's native chrome (menus, title bar, dialogs), use agent-desktop. For its web contents, launch it with a DevTools port and hand off: `agent-desktop launch <app> --cdp 9222 --activate`, then `agent-browser --cdp 9222 snapshot -i` (see `vercel-agent-browser`).
