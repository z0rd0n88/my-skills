---
name: pr-review-router
description: Use when open PRs in VistaMobileBE or Flutter-mobile-app (or one named PR) need a review posted as a PR comment, picking the review skill from what the diff touches. Built for unattended scheduled runs; never approves, merges, or pushes.
argument-hint: "[<owner>/<repo> <N>] [--max <n>] [--dry-run] | -h"
---

# pr-review-router

## `-h` / `--help`

If the argument text (trimmed, case-insensitive) is exactly `-h`, `--help`, or
`help`, output only the block below and stop. Do not run any other step in this
skill.

> **⚠️ Posts one comment per reviewed PR, and each review can use up to four agents.**
> Read-only on code: it never approves, requests changes, merges, pushes, or edits a PR branch.

Finds open PRs that have no review of their current head commit yet, picks the review skill from
what each diff touches, runs it in read-only mode, and posts the result as one PR comment.

| Option | Values | Default | Effect |
|---|---|---|---|
| target | `<owner>/<repo> <N>` or nothing | scan every repo in the table below | Review one PR, or scan for PRs that need a review. |
| `--max <n>` | integer 1–10 | 3 | Most PRs reviewed in one run (scan mode only). |
| `--dry-run` | flag | off | Print the plan (PR → skill) and the composed bodies; post nothing. |

## Repos

| Repo | Checkout (sibling of this session's other repos) | Code review skill |
|---|---|---|
| `VistaMarkets/VistaMobileBE` | `VistaMobileBE/` | `vista-dw-review` (repo-local; picks Vista's reviewer agents) |
| `VistaMarkets/Flutter-mobile-app` | `Flutter-mobile-app/` | `dw-review` (generic), with `flutter analyze` attached |

Find a checkout by its remote, not by guessing a path:

```bash
for d in /home/user/*/ "$PWD"/../*/; do
  url=$(git -C "$d" remote get-url origin 2>/dev/null) || continue
  case "$url" in *"$REPO"|*"$REPO".git) echo "$(cd "$d" && pwd)"; break;; esac
done
```

No checkout for a repo means skip it and say so in the summary. Never clone a repo from here.

## Hard rules

1. **Running this skill is the operator's go-ahead to post.** The sub-skills ask for a go-ahead
   before they publish. This skill answers that question for them: tell each sub-skill **not to
   post** (it returns the report instead), and post the report yourself in Step 5. That gives one
   comment per PR, with a marker on it.
2. **Read-only on the PR.** Never approve, request changes, merge, push, resolve threads, or run
   a fix loop. Call `Z0rd0nZords:zord-multi-agent-review` only with `--no-loop --no-comment`.
   Never call `perseus08-rvw-agy`, `finding-fixer`, or `pr-merge-cleanup` from here: those
   merge or edit.
3. **REST, not GraphQL.** In cloud sessions `gh pr …` and `gh issue …` fail with a 403 (the proxy
   blocks GraphQL). Use `gh api repos/{owner}/{repo}/…` for everything, or the GitHub MCP tools.
4. **Never fake a review.** If a sub-skill fails or returns no report, post nothing for that PR
   and list it under "failed" in the summary. A short note pretending to be a review is worse
   than no comment.

## Step 1 — candidates

With a target, the candidate is that one PR (skip the marker check in Step 2 only if the operator
asked for a re-review). Otherwise, for each repo in the table:

```bash
gh api "repos/$REPO/pulls?state=open&sort=updated&direction=desc&per_page=50" \
  --jq '.[] | select(.draft|not) | [.number, .head.sha, .user.login, ([.labels[].name]|join(",")), .title] | @tsv'
```

Drop a PR when its labels include `skip-review` or `no-bot-review`.

## Step 2 — already reviewed?

Every comment this skill posts starts with a marker naming the head commit it reviewed:

```
<!-- pr-review-router sha=<head_sha> skill=<skill-name> -->
```

Skip a PR when one of its issue comments already has the marker for its **current** head sha:

```bash
gh api "repos/$REPO/issues/$N/comments" --paginate --jq '.[].body' \
  | grep -qF "pr-review-router sha=$HEAD_SHA" && echo reviewed
```

A new push changes the head sha, so the PR becomes a candidate again. Keep the first `--max`
candidates, most recently updated first, across all repos. Name the rest in the summary as
"deferred to the next run".

## Step 3 — classify

```bash
gh api "repos/$REPO/pulls/$N/files" --paginate \
  --jq '.[] | [.filename, .status, (.additions+.deletions)] | @tsv' > "$SCRATCH/files-$N.tsv"
```

Take the **first** row that matches:

| # | Class | Rule | Skill |
|---|---|---|---|
| 1 | Spec / design doc | Every changed file is Markdown under `docs/`, or a file named like `*spec*`, `*prd*`, `*design*`, or `adr*`, **and** none of them is an instruction file (see below) | `Z0rd0nZords:zord-reasoned-review` with the changed doc paths, read from a worktree at the PR head |
| 2 | Large | More than 40 files, or more than 1500 changed lines in total | `Z0rd0nZords:zord-multi-agent-review pr <N> --no-loop --no-comment --adversarial` |
| 3 | VistaMobileBE code | Repo is `VistaMarkets/VistaMobileBE` | `vista-dw-review pr <N>` |
| 4 | Flutter code | Repo is `VistaMarkets/Flutter-mobile-app` | `dw-review pr <N>`, plus Step 4b |

Instruction files are `AGENTS.md`, `CLAUDE.md`, `SKILL.md`, `REVIEW.md`, and anything under
`.claude/`, `.agents/`, or `.codex/`. A PR that changes them is code-class (rows 2–4): the dw-review
lanes check instruction drift, but the reasoned-review lenses do not.

**Add-on, any class except 1:** if a changed non-test source file (`.kt`, `.kts`, `.sql`, `.dart`,
`.ts`, `.py`) matches money terms in its patch
(`price|qty|quantity|amount|fee|balance|notional|slippage|funding|pnl|margin|collateral|order`),
also run `audit-numeric-types` on the PR diff and attach its PASS/FAIL section.

Run every skill from inside that repo's checkout, so repo-local skills and `.claude/agents/`
resolve.

## Step 4 — run

Brief each sub-skill with one sentence before its arguments: *"Unattended run from
pr-review-router: do not post to GitHub or write a record file to the repo; return the final
report as your output."* Then:

- **4a.** Run the chosen skill. Keep its final report verbatim, including the verdict and any
  author questions.
- **4b. Flutter only.** Run static analysis on the PR head in a throwaway worktree, once per
  Dart package the PR touches. Do not analyze from the repo root: the root `analysis_options.yaml`
  excludes `vista/app`, which is its own package, so a root-level run reports "No issues found"
  without reading the changed files.

  ```bash
  W="$SCRATCH/flutter-pr-$N"
  git -C "$CHECKOUT" fetch -q origin "pull/$N/head:pr-review-$N"
  git -C "$CHECKOUT" worktree add -q "$W" "pr-review-$N"
  : > "$SCRATCH/analyze-$N.txt"
  # nearest pubspec.yaml above each changed .dart file = the package to analyze
  for f in $(cut -f1 "$SCRATCH/files-$N.tsv" | grep '\.dart$'); do
    d=$(dirname "$f"); while [ "$d" != "." ] && [ ! -f "$W/$d/pubspec.yaml" ]; do d=$(dirname "$d"); done; echo "$d"
  done | sort -u > "$SCRATCH/packages-$N.txt"
  while read -r pkg; do
    echo "== flutter analyze in $pkg" >> "$SCRATCH/analyze-$N.txt"
    (cd "$W/$pkg" && flutter pub get >/dev/null 2>&1 && flutter analyze --no-fatal-infos) >> "$SCRATCH/analyze-$N.txt" 2>&1
    echo "exit=$?" >> "$SCRATCH/analyze-$N.txt"
  done < "$SCRATCH/packages-$N.txt"
  git -C "$CHECKOUT" worktree remove --force "$W"; git -C "$CHECKOUT" branch -D -q "pr-review-$N"
  ```

  No changed `.dart` file means no analyze section. No `flutter` on PATH means writing
  "flutter analyze: not run (no SDK in this session)", never silently dropping the section.
- **4c.** Run the add-on from Step 3, if it applies.

## Step 5 — post

Compose one body in `$SCRATCH/review-$REPO_SLUG-$N.md`:

```markdown
<!-- pr-review-router sha=<head_sha> skill=<skill-name> -->
## Automated review — <skill-name> @ <short_sha>

<sub-skill report, verbatim>

<details><summary>flutter analyze</summary>        <!-- Flutter only -->

<each package's result from analyze-N.txt, last 60 lines at most, in a code fence>
</details>

<audit-numeric-types section>                      <!-- add-on only -->

<sub>Routed by pr-review-router: <class> → <skill-name>. Read-only review; it does not approve or block merges.</sub>

---
_Generated by [Claude Code](https://claude.ai/code)_
```

GitHub caps a comment at 65,536 characters. Over that, keep every CRITICAL and HIGH finding in
full, shrink MEDIUM and LOW to a table of `file:line` and one-line summaries, and say that you did.

With `--dry-run`, print the body and stop. Otherwise, post the comment:

```bash
gh api "repos/$REPO/issues/$N/comments" -F "body=@$SCRATCH/review-$REPO_SLUG-$N.md" --jq .html_url
```

Check that the head sha did not move while the review ran (`gh api repos/$REPO/pulls/$N --jq
.head.sha`). If it moved, post anyway, keeping the reviewed sha in the marker and the heading, so
the next run reviews the new head.

## Step 6 — summary

End with one table: repo, PR, class, skill, verdict, and the comment URL, or `skipped (reason)`,
`deferred`, or `failed (reason)`. That table is the whole output of a scheduled run.
