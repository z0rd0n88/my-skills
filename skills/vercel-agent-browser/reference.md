# agent-browser reference

Condensed from https://agent-browser.dev and `agent-browser skills get core` (v0.41.2). For a flag not listed here: `agent-browser --help`, `agent-browser skills get core --ref commands`, or the per-page markdown at `https://agent-browser.dev/<page>.md` (index: `https://agent-browser.dev/llms.txt`). All examples omit `--session <name>`; add it to every real call.

## How it runs

A Rust CLI talks to a background daemon that holds Chrome over CDP. The daemon starts on the first command and stays up between commands. It shuts down after 1 hour idle (`--idle-timeout <time>`, `0` disables) and discards tabs and cookies unless `--restore` is set. Headed browsers and user-attached browsers are exempt from the idle timeout.

## Reading a page

| Need | Command |
|---|---|
| Interactive elements with refs | `snapshot -i` |
| Full tree | `snapshot` |
| Include link hrefs | `snapshot -i -u` |
| Drop empty structural nodes | `snapshot -i -c` |
| Scope to a CSS region | `snapshot -s "#main"` |
| Full state once, then only changes | `snapshot -i --delta` |
| Machine-readable | `snapshot -i --json` |
| Text of a docs page (no Chrome) | `read <url>`, `read <url> --outline`, `read <url> --filter <word>` |
| Element text or attribute | `get text @e1`, `get attr @e1 href`, `get url`, `get title`, `get value @e1`, `get count <sel>` |
| Run JS | `eval "<expr>"`; anything with quotes: `eval --stdin` with a quoted heredoc |

Snapshot lines look like `@e3 [input type="email"] placeholder="Email"`. Iframe contents are inlined, so their refs work directly; `frame @eN` scopes to one frame, `frame main` returns.

## Acting

| Need | Command |
|---|---|
| Click / open in new tab | `click @e1`, `click @e1 --new-tab` |
| Clear and type / append | `fill @e2 "text"`, `type @e2 " more"` |
| Key at focus | `press Enter`, `press Control+a` |
| Dropdown | `select @e4 "value-or-label"` |
| Checkbox, hover, focus, double-click | `check`, `uncheck`, `hover`, `focus`, `dblclick` + `@ref` |
| Upload | `upload @e5 file.pdf` |
| Scroll | `scroll down 500`, `scrollintoview @e1` |
| Drag | `drag @e1 @e2` |
| No ref yet | `find role button click --name "Submit"`, `find text "Sign In" click`, `find label "Email" fill "a@b.c"` |
| Custom input ignores fill | `focus @e1` then `keyboard inserttext "text"` (or `keyboard type` for real keystrokes) |
| confirm / prompt dialogs | `dialog status`, `dialog accept [text]`, `dialog dismiss`; alert and beforeunload auto-accept |

## Waiting

`wait @e1` · `wait --text "Success"` · `wait --url "**/path"` · `wait --fn "window.app.ready"` · `wait --load load|domcontentloaded`. Default timeout 25 s (`--timeout`, `AGENT_BROWSER_DEFAULT_TIMEOUT`). Use `networkidle` only for pages known to go quiet.

## Capturing

- `screenshot page.png` (path optional), `--full` for the full scroll height, `--annotate` labels `[N]` matching `@eN`, `--if-changed` skips unchanged frames.
- `pdf out.pdf` · `record start out.webm [url]` / `record stop` · `trace start` / `trace stop [path]`.
- `diff snapshot` (against the last snapshot), `diff screenshot --baseline img.png`, `diff url <u1> <u2>`.
- Debug: `console [--clear]`, `errors [--clear]`, `network ...`, `vitals [url]`, `a11y [url]`.

## Tabs, sessions, state

- Tabs: `tab` lists stable ids (`t2`), `tab new <url>`, `tab t2`, `tab close t2`. Refs from another tab are invalid after a switch. `"revived": true` means the tab was reloaded and in-page state is gone.
- Parallel browsers: one `--session <name>` each, each with its own cookies, tabs, and refs. Sharing one Chrome via `--cdp <port>` needs `--pin-tab`.
- Keep a login across runs: `--restore` (key = session name) saves cookies and localStorage on close and periodically. Inspect with `session info --json`.
- Reuse a real Chrome profile: `--profile <name|path>`; attach to a running Chrome: `--auto-connect` or `--cdp <port|url>`.
- Auth vault: `auth save|login|list|show|delete <name>`. Set `AGENT_BROWSER_ENCRYPTION_KEY` before the first save or one is generated.
- Lock navigation for sensitive work: `--allowed-domains a.com,b.com`.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Ref not found / Element not found | Page changed. Snapshot again. |
| Stale ref cannot be recovered | Element replaced and duplicates made the match ambiguous; nothing ran. Snapshot again. |
| `page_wedged` | Tab stopped responding; a launched browser swaps in a blank tab. Navigate again. |
| In DOM but not in snapshot | Off-screen or not rendered. Scroll or `wait --text`, then snapshot. |
| Click does nothing / `covered by <...>` | Overlay on top. Dismiss it first. |
| Cross-origin iframe missing | Try `frame "#iframe"`, else `eval` in that origin. |
| WebGPU screenshot is black | Relaunch with `--webgpu`, wait for a frame. |
| Anything else odd | `agent-browser doctor` (`--fix` runs destructive repairs: ask first). |

## Specialized guides served by the CLI

`agent-browser skills get <name>`; `skills list` shows what the installed version has.

| Name | When |
|---|---|
| `electron` | Electron apps (VS Code, Slack, Discord, Figma) over CDP |
| `slack` | Slack workspace tasks |
| `dogfood` | Exploratory QA and bug hunts with a report |
| `derive-client` | Record a HAR, generate an API client for a site |
| `webmcp-gen` | Build WebMCP tools for a page |
| `vercel-sandbox`, `protected-vercel-deployments`, `agentcore` | Vercel Sandbox microVMs, protected Vercel deployments, AWS AgentCore cloud browsers |

Core-guide sub-references load with `skills get core --ref <stem>`: `commands`, `snapshot-refs`, `authentication`, `session-management`, `trust-boundaries`, `video-recording`, `profiling`, `streaming`, `proxy-support`, `webgpu`.
