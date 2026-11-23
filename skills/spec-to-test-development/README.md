# spec-to-test-development

One command takes a feature or build request to working code. A fresh session writes the spec, a
second fresh session writes failing tests from that spec alone, and the main session implements
against tests it is not allowed to change. The design insight:

> Tests only catch a misreading of the request when they are written by something that did not
> also write the code, so the test writer is given the spec and nothing else.

```
/spec-to-test-development add ISO 8601 duration parsing to the scheduler
```

## Why this skill exists

It came out of evaluating [agent-mcts](https://github.com/natsu0529/agent-mcts), a harness that
wraps Claude Code in a tree search over several attempts. Its own published benchmark (v0.4.1,
three small Python tasks, Haiku, 10 to 20 runs per setting) showed where the gain was:

| Setting | Answer better than a single attempt | Worse | Time | Cost per run |
|---|---|---|---|---|
| Search scored on the existing tests | 1 of 20 | 1 of 20 | about 5 min | $0.43 |
| Search scored by an LLM judge | 11 of 20 | 4 of 20 | about 21 min | $1.81 |
| Search scored on tests an agent wrote from the task | 16 of 20 | 2 of 20 | about 19 min | $2.44 |

What shaped this skill:

- **The gain came from the tests, not the search.** With only the existing tests, searching was
  no better than one attempt. With tests written from the task by a separate agent, the hidden
  test pass rate rose from 88% to 93%, and 32 of 40 revisions improved on their parent because a
  failing test told the next attempt what to fix.
- **The search was the expensive part.** Roughly four times the wall time and five to six
  times the cost, for a tree that was three attempts plus two revisions.
- **Generated tests can encode the bug.** On a vague bug report about misaligned Japanese text,
  the test writer measured alignment in characters, as the buggy code did. The unfixed
  code passed, every real fix failed, and the tool returned the unfixed code in 10 of 10 runs.

So the skill keeps the part that worked, independent tests written before the code, and drops the
tree search. The failure case is why a spec comes first and why every new test must fail before
any code is written.

## How it works

| Step | Who | Sees | Produces |
|---|---|---|---|
| 0. Preflight | main session | the repository | clean tree, feature branch, test command, baseline |
| 1. Spec | fresh session | the typed request and the repository | `docs/specs/<slug>.md`: pinned interface, numbered behaviours with examples, numbered assumptions |
| 2. Tests | second fresh session | the spec and the repository, never the request | failing tests, committed with the spec as the freeze point |
| 3. Implement | main session | everything | code that turns the suite green without touching the frozen tests |
| 4. Verify | main session | | full suite passing, `git diff --quiet` against the freeze point, implementation commit |
| 5. Report | main session | | outcome, assumptions made on your behalf, tests added, disputes, commits |

## Design decisions

- **Two fresh sessions, not one.** If one session wrote both the spec and the tests, its unstated
  assumptions would reach the tests without being written down. Splitting them makes the
  spec file the only channel, so every assumption has to be on the page where you can read it.
- **The spec session gets only what you type after the command.** Anything you want in the spec
  belongs in the request.
- **Main session only.** The main session holds the request and is the one that can launch fresh
  sessions and ask you a question. A subagent running the skill would either write the tests
  itself, which removes the independence, or launch sessions nobody can answer.
- **No approval stop by default.** The point is one command. It may ask you two things: the test
  command when it cannot find one, and one round of questions when the request has two readings
  that behave differently and the code does not settle which. `--gate` adds a pause after the
  spec if you want to read it first.
- **Frozen tests are checked, not trusted.** The spec and tests are committed before any source
  changes, and step 4 compares the test files against that commit. A test the main session
  thinks is wrong goes to another fresh session, which sees the spec and the test but not the
  implementation, and either amends or upholds it.
- **It commits but never pushes.** Two local commits on a feature branch, so the freeze check has
  something to compare against and you decide what leaves your machine.
- **Frontmatter is only `name` and `description`.** That is what a claude.ai upload accepts, and
  uploading is how a personal skill reaches cloud and Cowork sessions. The cost is that
  "user-invoked only" is an instruction in the body, not a setting Claude Code enforces.

The reason behind each rule is in [`references/rationale.md`](references/rationale.md).

## When not to use it

Requests with no behaviour a test can observe: styling, copy, configuration, glue code. The spec
session replies `NOT-SPECABLE` and the skill stops and offers to do the work directly. The
benchmark above only showed a gain where the behaviour could be written down, so a vague request
is worth tightening before you run this.

## Using it in cloud sessions

Cloud and Cowork sessions do not read `~/.claude/skills/` on your machine. Either enable the
skill for your claude.ai account by uploading the folder as a zip, or commit it to the
`.claude/skills/` directory of the repository you are working in.

## Status

- Followed by hand once, end to end, on a throwaway Python repository with the vague bug report
  above. The spec session specified terminal display width instead of character count, the test
  session wrote 34 tests from the spec alone (18 red, 16 green for behaviour marked existing),
  and the implementation went green with the frozen tests unchanged.
- That run predates later wording changes. The three scenarios in `evals/evals.json` have not
  been run, and it has not been run as an installed command or through a claude.ai upload.
- Audited with `skill-sheriff-cc` against the official skill docs. The one open item is that the
  name is not a gerund.

## Files

| File | What it is |
|---|---|
| `SKILL.md` | The steps the main session follows |
| `references/spec-brief.md` | Instructions for the fresh session that writes the spec |
| `references/test-brief.md` | Instructions for the fresh session that writes the tests and rules on disputes |
| `references/rationale.md` | The reason behind each rule, for people changing the skill |
| `evals/` | Three scenarios, a small fixture repository, and a note on how to run them |
