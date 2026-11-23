#!/usr/bin/env python3
"""Fail when SKILL.md's -h table and references/flags.md list different flags.

The two tables drifted once already: --lenses shipped in the per-flag table but
not in -h, so --help hid it (fixed in #190). Rows marked internal/reserved in
flags.md are exempt, since -h lists only user-facing flags.

    python3 check_flag_tables.py [skill_dir]

Exit 0 = in sync, 1 = drift, 2 = the check could not run (missing file, no -h
heading, or a table that parses to zero flags). .githooks/pre-commit runs it.
"""

import re
import sys
from pathlib import Path

FLAG = re.compile(r"`(--[a-z][a-z-]*)")


def table_rows(text):
    # Split on unescaped pipes only: cells like `--high-cap <n\|off>` contain one.
    return [
        re.split(r"(?<!\\)\|", line)
        for line in text.splitlines()
        if line.startswith("| `")
    ]


def help_flags(skill_md):
    section = skill_md.split("## `-h` / `--help`", 1)[1].split("\n## ", 1)[0]
    return {flag for row in table_rows(section) for flag in FLAG.findall(row[1])}


def reference_flags(flags_md):
    return {
        flag
        for row in table_rows(flags_md)
        if not re.search(r"internal|reserved", row[2], re.I)
        for flag in FLAG.findall(row[1])
    }


def main(skill_dir):
    try:
        in_help = help_flags((skill_dir / "SKILL.md").read_text())
        in_ref = reference_flags((skill_dir / "references" / "flags.md").read_text())
    except (OSError, IndexError) as exc:
        print(f"error: could not read the flag tables: {exc!r}", file=sys.stderr)
        return 2
    if not in_help or not in_ref:
        # Two empty sets compare equal; never report that as "in sync".
        print("error: a flag table parsed to zero flags", file=sys.stderr)
        return 2
    for where, missing in (
        ("SKILL.md -h table", in_ref - in_help),
        ("references/flags.md", in_help - in_ref),
    ):
        for flag in sorted(missing):
            print(f"missing from {where}: {flag}")
    return int(in_help != in_ref)


if __name__ == "__main__":
    default = Path(__file__).resolve().parent.parent
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else default))
