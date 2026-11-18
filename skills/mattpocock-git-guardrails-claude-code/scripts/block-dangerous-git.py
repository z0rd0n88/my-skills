"""Decide whether a Bash command runs a dangerous git operation. Exit 2 = block, 0 = allow.

Reads the PreToolUse hook JSON on stdin. Fails closed: anything it can't parse is blocked.
ponytail: shlex is not a full shell. Git aliases defined in config files, scripts that
call git, and variables expanded at run time ("$CMD") still get through; it's a speed
bump, not a sandbox.
"""
import json
import os
import re
import shlex
import sys
from typing import Iterator, NoReturn

SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
# git global options that take the next word as their value
GIT_OPTS_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--super-prefix", "--config-env"}
# git global options that take no value; any other option is blocked rather than guessed at
GIT_OPTS_NO_VALUE = {
    "-p", "--paginate", "-P", "--no-pager", "--bare", "--no-replace-objects", "--no-lazy-fetch",
    "--no-optional-locks", "--no-advice", "--literal-pathspecs", "--glob-pathspecs",
    "--noglob-pathspecs", "--icase-pathspecs", "--exec-path", "--html-path", "--man-path",
    "--info-path", "-v", "--version", "-h", "--help",
}
# short options that take a value, per subcommand, so the value's letters aren't read as flags
VALUED_SHORTS = {"clean": "e", "branch": "u"}
WHOLE_TREE = {".", "./", ":/", ":/.", "*"}
OPERATORS = set(";&|()<>")


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


def parse_opts(rest: list[str], valued: str) -> tuple[str, list[str], list[str]]:
    """Split subcommand args like git does: (short flag letters, long options, positionals)."""
    letters, longs, positionals = "", [], []
    skip = False
    for k, arg in enumerate(rest):
        if skip:
            skip = False
        elif arg == "--":
            positionals += rest[k + 1:]
            break
        elif arg.startswith("--"):
            longs.append(arg)
        elif arg.startswith("-") and len(arg) > 1:
            for n, ch in enumerate(arg[1:]):
                letters += ch
                if ch in valued:  # the rest of the word, or the next word, is its value
                    skip = n == len(arg) - 2
                    break
        else:
            positionals.append(arg)
    return letters, longs, positionals


def substitutions(command: str) -> list[str]:
    """Bodies of every `...` and $(...), quoted or not, so they get checked on their own."""
    bodies = re.findall(r"`([^`]*)`", command)
    i = command.find("$(")
    while i != -1:
        depth, j = 1, i + 2
        while j < len(command) and depth:
            depth += {"(": 1, ")": -1}.get(command[j], 0)
            j += 1
        bodies.append(command[i + 2:j - 1] if depth == 0 else command[i + 2:])
        i = command.find("$(", i + 2)
    return bodies


def segments(command: str) -> Iterator[list[str]]:
    """Split a command line into simple commands (word lists) at shell operators."""
    for sub in ("`", "$("):  # unquoted substitutions become their own commands
        command = command.replace(sub, " ; ")
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()<>")
    lexer.whitespace_split = True
    seg: list[str] = []
    for word in lexer:  # raises ValueError on unbalanced quotes
        if word and set(word) <= OPERATORS:
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
        opt, _, attached = args[i].partition("=")
        if opt in GIT_OPTS_WITH_VALUE:
            value = attached if attached else (args[i + 1] if i + 1 < len(args) else "")
            if opt in ("-c", "--config-env") and value.lower().startswith("alias."):
                return "an inline git alias (-c alias.*)"
            i += 1 if attached else 2
        elif opt in GIT_OPTS_NO_VALUE or attached:
            i += 1
        else:
            return f"an unknown git option ({args[i]})"
    if i >= len(args):
        return None
    sub, rest = args[i], args[i + 1:]
    letters, longs, positionals = parse_opts(rest, VALUED_SHORTS.get(sub, ""))
    if sub == "push":
        return "git push"
    if sub == "reset" and any(long_opt(a, "--hard", "--h") for a in longs):
        return "git reset --hard"
    if sub == "clean" and not ("n" in letters or any(long_opt(a, "--dry-run", "--d") for a in longs)):
        return "git clean without --dry-run"
    if sub == "branch":
        delete = "d" in letters or any(long_opt(a, "--delete", "--de") for a in longs)
        force = "f" in letters or any(long_opt(a, "--force", "--fo") for a in longs)
        if "D" in letters or (delete and force):
            return "git branch force-delete"
    if sub in ("checkout", "restore") and any(a in WHOLE_TREE for a in positionals):
        return f"git {sub} of the whole tree"
    return None


def check(command: str, depth: int = 0) -> None:
    if depth > 5:
        block("the command nests too deeply to check.")
    command = command.replace("\\\n", "")  # line continuations
    for body in substitutions(command):
        check(body, depth + 1)
    for seg in segments(command):
        for j, word in enumerate(seg):
            name = os.path.basename(word)
            if name == "git":  # also /usr/bin/git, `env git`, `xargs git`
                reason = dangerous_git(seg[j + 1:])
                if reason:
                    block(f"'{command}' runs {reason}.")
            elif name in SHELLS and any("c" in short_flags(w) for w in seg[j + 1:]):
                for script in seg[j + 1:]:  # sh -c [--] '...': check every word that follows
                    if not script.startswith("-"):
                        check(script, depth + 1)
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
