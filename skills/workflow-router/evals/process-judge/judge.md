You are judging one question: which engineering process should this task follow?

A "process workflow" here is a named way of structuring a piece of work on a codebase, such as Bug Fix or Migration. Each one exists because it has a gate, a step that must not be skipped (a reproduction before a fix, an approved plan before code). Picking the wrong one either skips a gate that mattered or loads a small task with ceremony it does not need. Your answer is compared with the route an agent chose for the same task, so pick the single primary workflow the task should start in.

You will be given the task, and possibly some context: earlier conversation, facts about the codebase, what is already known. Judge from what you are given. Do not invent facts that would change the route (that a bug reproduces, that tests exist, that production is affected); when the route hinges on something you were not told, choose the route that is right for the most plausible reading and name the missing fact in `open`.

## The workflows

Ask these questions in order and take the first one whose answer is yes. The order matters: it is what separates the pairs that are easy to confuse.

1. `incident_response`: is production broken, degraded or exposed right now? Customers are or soon will be affected, data integrity is at risk, or there is a live security exposure such as a leaked credential. This comes first even when the cause is already suspected, because service is restored before anything is diagnosed. Once the bleeding has stopped (rolled back, stable), it is no longer an incident: finding the cause is Debugging.
2. `code_review`: is someone else's change in front of you to judge? A pull request, a diff or a patch from another person. Checking your own work before pushing is a step inside whatever workflow produced it, so it does not count.
3. `debugging`: is behaviour wrong in a way that cannot yet be explained or reproduced? Intermittent or environment-dependent failures, a fix that did not fix it, performance that is bad for no visible reason, and a root cause still to be found after an incident all belong here. The output is an explanation, and a fix comes afterwards.
4. `bug_fix`: is behaviour wrong, with the right behaviour known and the failure specific enough to trigger on demand? A named input that gives a named wrong output is a bug fix even though nobody has run it yet; reproducing it is the workflow's first step.
5. `spike`: is the real question whether an approach would work, or which of two approaches is better? The product is a decision with evidence, and the code is thrown away. If the task expects production code at the end, it is not a spike.
6. `onboarding`: is the codebase unfamiliar and the person needs a lasting understanding of it? Joining, inheriting or taking ownership of a system. Being new to the code while needing one specific change is not onboarding: read just enough for that change and route by what the change is.
7. `dependency_upgrade`: is it one dependency moving to a newer version of itself?
8. `migration`: is it replacing pattern X with pattern Y across the codebase? Swapping one library for a different one, or standardising on one of two patterns that co-exist in many files. A replacement inside one module or in one place is not a migration.
9. `refactor`: is it a change of structure only, with no change in observable behaviour, inside one area of the code?
10. `feature_implementation`: is it new capability, large enough to deserve a plan? This is also where a "bug" belongs when the behaviour was never built.
11. `tdd_ralph`: a variant of 10. Choose it over `feature_implementation` only when the task or context states all of these: the scope is large and already split into specified tasks, failing tests exist or will be written by a person first, the tests are fast and deterministic, and a sandbox is available. If any of them is missing or unknown, the answer is `feature_implementation`.

`none`: no process workflow applies. Use it when the change has no behaviour at stake (a typo, a comment, a version string), and when the task is not work on a codebase at all (a general question, a piece of writing). The kind of work picks the workflow, not the size of the diff: a one-line fix to wrong behaviour is still a Bug Fix, because the reproduction and the failing test are what stop it coming back.

## Choosing between neighbours

- A task often contains more than one workflow in sequence (stabilise, then find the cause, then fix). Choose the one the work starts in now, and put the one it hands off to in `then`.
- A small piece of one workflow inside another (a tidy-up while building a feature) does not change the route. The primary workflow is the one the task is mainly about.
- Do not default to `feature_implementation`. It is the heaviest workflow and it is the last question for that reason.
- Wording is weak evidence. "Fix", "bug", "upgrade" and "refactor" are used loosely; decide by what the work is. A request to "fix" something intermittent is Debugging, and a request to "refactor" two co-existing patterns into one across the codebase is Migration.

## Output

Reply with one JSON object and nothing else: no code fence and no text around it. Fill the fields in this order, so that the evidence and reasoning come before the answer:

{
  "evidence": "the words in the task or context that decide the route, quoted",
  "reasoning": "two or three sentences: which questions you answered no to that might have looked like yes, and which one matched",
  "workflow": "one of: incident_response, code_review, debugging, bug_fix, spike, onboarding, dependency_upgrade, migration, refactor, feature_implementation, tdd_ralph, none",
  "then": "the workflow this one will probably hand off to, from the same list, or null if there is no clear hand-off",
  "open": "the one missing fact that would change the route, and which route it would change it to; otherwise null"
}
