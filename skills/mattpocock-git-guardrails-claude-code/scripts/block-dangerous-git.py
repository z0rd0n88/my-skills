"""Decide whether a Bash command runs a dangerous git operation. Exit 2 = block, 0 = allow.

Reads the PreToolUse hook JSON on stdin. Fails closed: anything it can't parse is blocked.
ponytail: shlex is not a full shell. Git aliases, scripts that call git, and variables
expanded at run time ("$CMD") still get through; it's a speed bump, not a sandbox.
"""
import json
import os
import shlex
import sys
from typing import Iterator, NoReturn

SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
# git global options that take the next word as their value
GIT_OPTS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env", "--exec-path"}
WHOLE_TREE = {".", "./", ":/", ":/.", "*"}


def block(reason: str) -> NoReturn:
    print(f"BLOCKED: {reason} The user has prevented you from doing this.", file=sys.stderr)
    sys.exit(2)


def long_opt(arg: str, name: str, shortest: str) -> bool:
    """True if arg is `name` or an abbreviation of it git would accept (at least `shortest` long)."""
    flag = arg.split("=", 1)[0]
    return len(flag) >= len(shortest) and name.startswith(flag)


def short_flags(arg: str) -> str:
    """Letters of a bundled short-option word like -df, else ''."""
    return arg[1:] if arg.startswith("-") and not arg.startswith("--") else ""


def segments(command: str) -> Iterator[list[str]]:
    """Split a command line into simple commands (word lists) at shell operators."""
    command = command.replace("\\\n", "")  # line continuations
    for sub in ("`", "$("):  # command substitutions become their own commands
        command = command.replace(sub, " ; ")
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()<>")
    lexer.whitespace_split = True
    seg = []
    for word in lexer:  # raises ValueError on unbalanced quotes
        if word and set(word) <= set(";&|()<>"):
            if seg:
                yield seg
            seg = []
        else:
            seg.append(word)
    if seg:
        yield seg


def dangerous_git(args: list[str]) -> str | None:
    """args = the words after `git`. Returns a reason string or None."""
    i = 0
    while i < len(args) and args[i].startswith("-"):  # global options
        i += 2 if args[i] in GIT_OPTS_WITH_VALUE else 1
    if i >= len(args):
        return None
    sub, rest = args[i], args[i + 1:]
    shorts = "".join(short_flags(a) for a in rest)
    if sub == "push":
        return "git push"
    if sub == "reset" and any(long_opt(a, "--hard", "--h") for a in rest):
        return "git reset --hard"
    if sub == "clean" and not ("n" in shorts or any(long_opt(a, "--dry-run", "--d") for a in rest)):
        return "git clean without --dry-run"
    if sub == "branch":
        delete = "d" in shorts or any(long_opt(a, "--delete", "--de") for a in rest)
        force = "f" in shorts or any(long_opt(a, "--force", "--fo") for a in rest)
        if "D" in shorts or (delete and force):
            return "git branch force-delete"
    if sub in ("checkout", "restore") and any(a in WHOLE_TREE for a in rest):
        return f"git {sub} of the whole tree"
    return None


def check(command: str, depth: int = 0) -> None:
    if depth > 5:
        block("the command nests shells too deeply to check.")
    for seg in segments(command):
        for j, word in enumerate(seg):
            name = os.path.basename(word)
            if name == "git":  # also /usr/bin/git, `env git`, `xargs git`
                reason = dangerous_git(seg[j + 1:])
                if reason:
                    block(f"'{command}' runs {reason}.")
            elif name in SHELLS:  # sh -c '...', bash -lc '...'
                for k, opt in enumerate(seg[j + 1:-1], start=j + 1):
                    if "c" in short_flags(opt):
                        check(seg[k + 1], depth + 1)
                        break
            elif word == "eval":
                check(" ".join(seg[j + 1:]), depth + 1)
        # git-free forms the original also caught, e.g. an alias: `g push --force`, `g reset --hard`
        if "push" in seg and any(long_opt(a, "--force", "--fo") or "f" in short_flags(a) for a in seg):
            block(f"'{command}' looks like a force push.")
        if "reset" in seg and any(long_opt(a, "--hard", "--h") for a in seg):
            block(f"'{command}' looks like reset --hard.")


def main() -> None:
    try:
        command = json.load(sys.stdin)["tool_input"]["command"]
    except Exception:
        block("the hook input could not be read.")
    if not isinstance(command, str) or not command.strip():
        block("the command was empty.")
    try:
        check(command)
    except ValueError:  # unbalanced quotes
        block(f"'{command}' could not be parsed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
