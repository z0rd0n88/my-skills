#!/usr/bin/env bash
# Checks .claude-plugin/marketplace.json against the repo:
#   1. every plugin lists its skills (an entry without `skills` would load all of skills/)
#   2. every listed skill folder exists and holds a SKILL.md
#   3. every skills/<name>/ is listed in exactly one plugin (an unlisted skill loads in no plugin)
#   4. there is no root commands/ folder (every plugin would load it; commands live in refs/commands/)
# Exit: 0 ok, 1 violation, 2 misconfigured.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 2
[ -f .claude-plugin/marketplace.json ] || { echo "error: .claude-plugin/marketplace.json not found" >&2; exit 2; }

python3 - <<'PY'
import json, os, sys

d = json.load(open(".claude-plugin/marketplace.json"))
fail = []
where = {}
for e in d.get("plugins", []):
    name = e.get("name", "?")
    skills = e.get("skills")
    if not skills:
        fail.append(f"{name}: no `skills` list, so it would load every folder in skills/")
        continue
    for path in skills:
        folder = os.path.normpath(path)
        if not os.path.isfile(os.path.join(folder, "SKILL.md")):
            fail.append(f"{name}: {path} has no SKILL.md")
        where.setdefault(os.path.basename(folder), []).append(name)

for skill in sorted(os.listdir("skills")):
    if not os.path.isdir(os.path.join("skills", skill)):
        continue
    plugins = where.get(skill, [])
    if len(plugins) != 1:
        fail.append(f"skills/{skill}: listed in {len(plugins)} plugins {plugins}; list it in exactly one")

if os.path.isdir("commands"):
    fail.append("commands/ exists: every plugin would load it; put commands in refs/commands/ instead")

for f in fail:
    print(f, file=sys.stderr)
if fail:
    sys.exit(1)
print(f"ok: {len(where)} skills across {len(d['plugins'])} plugins")
PY
