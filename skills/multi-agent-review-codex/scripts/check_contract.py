#!/usr/bin/env python3
"""Check help metadata, local references, and example invocation contracts.

Usage: python3 check_contract.py [skill_dir]
       python3 check_contract.py --validate <target> <args...>
       python3 check_contract.py --self-test

Exit 0: valid; 1: contract drift/invalid invocation; 2: unable to run the check.
No live agents, repository writes, or network calls. The pre-commit hook is
advisory, while this checker itself returns a failing status for drift.
"""

from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import re
import shlex
import sys
import unittest


NAME = "multi-agent-review-codex"
HELP = "## `-h` / `--help`"
FILES = ("SKILL.md", "references/pr-loop.md", "examples/invocations.md")
FLAG = re.compile(r"--[a-z][a-z-]*")
RESERVED = {"--in-subagent", "--in-loop", "--resume-stopped"}
LENSES = {"pre-mortem", "inversion", "first-principles", "red-team", "jobs-to-be-done"}

# Values, default, scope: these must match the single help table exactly.
OPTIONS = {
    "--reviewers": ("csv", "auto", "all"),
    "--synthesizer": ("name", "auto", "all"),
    "--mode": ("name", "none", "all"),
    "--prompt-prelude": ("path", "none", "all"),
    "--lenses": ("csv", "none", "one-shot"),
    "--adversarial": ("flag", "off", "all"),
    "--no-adversarial": ("flag", "off", "all"),
    "--refuters": ("integer 1-5", "3", "all"),
    "--max-refuters": ("integer >=1", "20", "all"),
    "--no-report-audit": ("flag", "off", "all"),
    "--high-cap": ("integer >=1 | off", "8", "all"),
    "--write-to": ("path", "docs/reviews/<date>-<slug>.md", "all"),
    "--no-write": ("flag", "off", "all"),
    "--force": ("flag", "off", "all"),
    "--no-comment": ("flag", "off", "all"),
    "--max-files": ("integer >=1", "50", "dir/slices"),
    "--max-slices": ("integer >=1", "6", "slices"),
    "--staged": ("flag", "off", "diff"),
    "--no-loop": ("flag", "off", "all"),
    "--inline": ("flag", "on", "all"),
    "--yes": ("flag", "off", "all"),
    "--max-iterations": ("integer 1-8", "1", "pr-loop"),
    "--high-and-up-only": ("flag", "off", "pr-loop"),
    "--no-smoke": ("flag", "off", "pr-loop"),
}


class CheckUnavailable(ValueError):
    """A structural input is missing; an empty check must never pass."""


def validate_option_value(token, value):
    """Validate one value independently of target scope and other options."""
    if not value.strip():
        raise ValueError(f"empty value: {token}")
    values = OPTIONS[token][0]
    if values.startswith("integer") and not (token == "--high-cap" and value == "off"):
        upper = {"--refuters": 5, "--max-iterations": 8}.get(token)
        if not value.isascii() or not value.isdigit() or int(value) < 1:
            raise ValueError(f"positive integer required: {token}")
        if upper and int(value) > upper:
            raise ValueError(f"maximum {upper}: {token}")
    if values == "csv":
        items = [item.strip() for item in value.split(",")]
        if not all(items) or len(set(items)) != len(items):
            raise ValueError(f"empty or duplicate CSV item: {token}")
        if token == "--lenses" and not set(items) <= LENSES:
            raise ValueError("unknown reasoning lens")
    if token == "--mode" and not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("mode must be a preset name, not a path")


def parse_options(args):
    """Collect positional targets and options without resolving host paths."""
    positional, supplied = [], {}
    tokens = iter(args)
    for token in tokens:
        if not token.startswith("-"):
            positional.append(token)
            continue
        if token not in OPTIONS:
            raise ValueError(f"unsupported option: {token}")
        if token in supplied:
            raise ValueError(f"duplicate option: {token}")
        if OPTIONS[token][0] == "flag":
            supplied[token] = True
            continue
        value = next(tokens, None)
        if value is None or value.startswith("--"):
            raise ValueError(f"missing value: {token}")
        validate_option_value(token, value)
        supplied[token] = value
    return positional, supplied


def validate_targets(target, positional, supplied):
    """Enforce target arity, PR syntax, and explicit or default slice caps."""
    count = len(positional)
    if (
        (target in {"pr", "dir", "file"} and count != 1)
        or (target == "diff" and count != 0)
        or (target == "spec" and count < 1)
        or (target == "slices" and count < 2)
    ):
        raise ValueError(f"wrong number of targets for {target}")
    if target == "pr" and not (
        re.fullmatch(r"[1-9][0-9]*", positional[0])
        or re.fullmatch(r"https://[^/]+/[^/]+/[^/]+/pull/[1-9][0-9]*/?", positional[0])
    ):
        raise ValueError("PR must be a positive number or an HTTPS pull-request URL")
    if target == "slices":
        cap = int(supplied.get("--max-slices", OPTIONS["--max-slices"][1]))
        if count > cap:
            raise ValueError(f"slice count {count} exceeds --max-slices {cap}")


def validate_combinations(target, supplied, loop):
    """Reject options outside their scope and conflicting or missing flags."""
    for flag in supplied:
        scope = OPTIONS[flag][2]
        valid = (
            scope == "all"
            or (scope == "pr-loop" and loop)
            or (scope == "one-shot" and not loop)
            or target in scope.split("/")
        )
        if not valid:
            raise ValueError(f"{flag} is only valid on {scope}")
    for left, right in (
        ("--no-write", "--write-to"),
        ("--adversarial", "--no-adversarial"),
    ):
        if left in supplied and right in supplied:
            raise ValueError(f"conflicting options: {left}, {right}")
    for flag, required in (
        ("--force", "--write-to"),
        ("--refuters", "--adversarial"),
        ("--max-refuters", "--adversarial"),
    ):
        if flag in supplied and required not in supplied:
            raise ValueError(f"{flag} requires {required}")


def validate_args(argv):
    """Validate syntax and combinations, leaving host/path checks to Codex."""
    args = list(argv)
    if args and args[0] == NAME:
        args.pop(0)
    if len(args) == 1 and args[0].lower() in {"help", "-h", "--help"}:
        return "help"
    if not args or args[0] not in {"pr", "dir", "file", "spec", "diff", "slices"}:
        raise ValueError("expected pr, dir, file, spec, diff, or slices")
    target = args.pop(0)
    positional, supplied = parse_options(args)
    validate_targets(target, positional, supplied)
    loop = target == "pr" and "--no-loop" not in supplied
    validate_combinations(target, supplied, loop)
    return "loop" if loop else "one-shot"


def help_metadata(skill):
    if HELP not in skill:
        raise CheckUnavailable("missing help heading")
    section = skill.split(HELP, 1)[1].split("\n## ", 1)[0]
    result = {}
    for line in section.splitlines():
        if not line.startswith("| `--"):
            continue
        cells = [
            cell.strip().replace(r"\|", "|").strip("`")
            for cell in re.split(r"(?<!\\)\|", line)[1:-1]
        ]
        if len(cells) != 5:
            raise CheckUnavailable(f"unreadable help row: {line}")
        flag = cells[0]
        if flag in result:
            raise ValueError(f"duplicate help row: {flag}")
        result[flag] = tuple(cells[1:4])
    if not result:
        raise CheckUnavailable("help table parsed to zero flags")
    return result


def audit_documents(root, documents):
    documented = help_metadata(documents["SKILL.md"])
    failures = []
    for flag in sorted(set(documented) | set(OPTIONS)):
        if documented.get(flag) != OPTIONS.get(flag):
            failures.append(
                f"help drift for {flag}: {documented.get(flag)!r}; expected {OPTIONS.get(flag)!r}"
            )
    for relative, content in documents.items():
        for flag in set(FLAG.findall(content)) - set(OPTIONS) - RESERVED - {"--help"}:
            failures.append(f"undocumented flag in {relative}: {flag}")
        for link in re.findall(r"\[[^\]]+\]\(([^)]+)\)", content):
            if re.match(r"[a-z]+://|#", link):
                continue
            path = (root / relative).parent / link.split("#", 1)[0]
            if not path.exists():
                failures.append(f"missing local reference in {relative}: {link}")
    blocks = re.findall(
        r"```text\n(.*?)```", documents["examples/invocations.md"], re.S
    )
    invocations = [
        line.strip()
        for block in blocks
        for line in block.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not invocations:
        raise CheckUnavailable("examples parsed to zero invocations")
    for command in invocations:
        try:
            tokens = shlex.split(command)
            if not tokens or tokens[0] != NAME:
                raise ValueError("wrong skill name")
            validate_args(tokens)
        except ValueError as exc:
            failures.append(f"invalid example: {command}: {exc}")
    return failures


def check(root):
    try:
        documents = {
            relative: (root / relative).read_text(encoding="utf-8")
            for relative in FILES
        }
        failures = audit_documents(root, documents)
    except (OSError, UnicodeError, CheckUnavailable) as exc:
        print(f"error: contract check did not run: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        failures = [str(exc)]
    for failure in failures:
        print(failure, file=sys.stderr)
    if not failures:
        print(
            "ok: Codex review help, option metadata, examples, and local references agree"
        )
    return int(bool(failures))


def self_test(root):
    """Exercise failure cases in memory; never alter the shipping documents."""

    class ContractTests(unittest.TestCase):
        @classmethod
        def setUpClass(cls):
            cls.docs = {
                name: (root / name).read_text(encoding="utf-8") for name in FILES
            }

        def test_current_documents_and_escaped_pipe(self):
            self.assertEqual(audit_documents(root, self.docs), [])
            self.assertEqual(
                help_metadata(self.docs["SKILL.md"])["--high-cap"],
                OPTIONS["--high-cap"],
            )

        def test_missing_flag_and_wrong_default_or_scope(self):
            mutations = [
                (
                    "\n".join(
                        line
                        for line in self.docs["SKILL.md"].splitlines()
                        if not line.startswith("| `--lenses`")
                    )
                ),
                self.docs["SKILL.md"].replace(
                    "| integer 1-8 | 1 | pr-loop |", "| integer 1-8 | 3 | pr-loop |"
                ),
                self.docs["SKILL.md"].replace("| 50 | dir/slices |", "| 50 | all |"),
            ]
            for skill in mutations:
                with self.subTest(skill_length=len(skill)):
                    self.assertTrue(
                        audit_documents(root, {**self.docs, "SKILL.md": skill})
                    )

        def test_empty_tables_and_examples_cannot_pass(self):
            with self.assertRaises(CheckUnavailable):
                help_metadata(HELP)
            with self.assertRaises(CheckUnavailable):
                help_metadata("# missing heading")
            with self.assertRaises(CheckUnavailable):
                audit_documents(
                    root, {**self.docs, "examples/invocations.md": "# empty"}
                )

        def test_bad_example_and_missing_link(self):
            bad = self.docs["examples/invocations.md"].replace(
                "diff --staged", "file src/x --staged"
            )
            self.assertTrue(
                audit_documents(root, {**self.docs, "examples/invocations.md": bad})
            )
            bad = self.docs["SKILL.md"].replace(
                "(references/pr-loop.md)", "(references/absent.md)"
            )
            self.assertTrue(audit_documents(root, {**self.docs, "SKILL.md": bad}))

        def test_compatibility_and_minimum_refuter_boundary(self):
            for command, mode in [
                ("pr 42 --no-loop --yes --inline", "one-shot"),
                ("pr 42 --max-iterations 1", "loop"),
                ("file a --no-loop --yes", "one-shot"),
                ("diff --adversarial --refuters 1", "one-shot"),
                ("--help", "help"),
            ]:
                with self.subTest(command=command):
                    self.assertEqual(validate_args(shlex.split(command)), mode)

        def test_invalid_combinations_and_bounds(self):
            for command in [
                "diff --max-iterations 1",
                "pr 42 --no-loop --no-smoke",
                "pr 42 --lenses inversion",
                "diff --refuters 2",
                "diff --adversarial --no-adversarial",
                "file a --staged",
                "file a --max-files 50",
                "diff --max-slices 2",
                "diff --write-to x --no-write",
                "diff --force",
                "pr 42 --max-iterations 9",
                "pr 42 --max-iterations 0",
                "diff --adversarial --refuters 6",
                "diff --high-cap 1.5",
                "spec a --lenses inversion,inversion",
                "spec a --lenses unknown",
                "diff --reviewers a,,b",
                "diff --mode ../bad",
                "diff --write-to",
                "diff --no-write --no-write",
                "diff --resume-stopped",
                "diff --in-subagent",
                "diff --in-loop",
                "slices one",
                "pr zero",
            ]:
                with self.subTest(command=command), self.assertRaises(ValueError):
                    validate_args(shlex.split(command))

        def test_missing_file_is_unavailable(self):
            with redirect_stderr(StringIO()):
                self.assertEqual(check(root / "__nonexistent_contract_fixture__"), 2)

        def test_explicit_slice_cap(self):
            for command in [
                "slices first second --max-slices 2",
                "slices --max-slices 3 first second third",
                "slices first --max-slices 2 second",
                "slices a b c d e f g --max-slices 7",
            ]:
                with self.subTest(command=command):
                    self.assertEqual(validate_args(shlex.split(command)), "one-shot")
            for command in [
                "slices first second --max-slices 1",
                "slices first second third --max-slices 2",
                "slices --max-slices 2 first second third",
            ]:
                with (
                    self.subTest(command=command),
                    self.assertRaisesRegex(
                        ValueError, "slice count .* exceeds --max-slices"
                    ),
                ):
                    validate_args(shlex.split(command))

        def test_default_slice_cap_and_spec_scope(self):
            self.assertEqual(
                validate_args(shlex.split("slices a b c d e f")), "one-shot"
            )
            with self.assertRaisesRegex(
                ValueError, "slice count 7 exceeds --max-slices 6"
            ):
                validate_args(shlex.split("slices a b c d e f g"))
            self.assertEqual(
                validate_args(shlex.split("spec a b c d e f g")), "one-shot"
            )

    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(ContractTests)
    )
    return int(not result.wasSuccessful())


if __name__ == "__main__":
    skill_root = Path(__file__).resolve().parent.parent
    args = sys.argv[1:]
    if args[:1] == ["--validate"]:
        try:
            print(validate_args(args[1:]))
            sys.exit(0)
        except ValueError as exc:
            print(f"invalid invocation: {exc}", file=sys.stderr)
            sys.exit(1)
    if args == ["--self-test"]:
        sys.exit(self_test(skill_root))
    if len(args) > 1 or (args and args[0].startswith("--")):
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    sys.exit(check(Path(args[0]) if args else skill_root))
