#!/usr/bin/env python3
"""Route a task with Jev (TypeSafe's System One model): process workflow, and orchestration fit.

  jev_route.py ask  '<task>' [context]     print the route as JSON
  jev_route.py eval <cases.jsonl> process|orchestration   score a case file
  jev_route.py hook                        UserPromptSubmit hook: read the event on stdin, suggest a route

One Jev call answers three questions (questions.json beside this file). The hook only suggests:
it never blocks a prompt, prints nothing when Jev is unsure or unreachable, and never tells the
agent that the user opted in to a workflow, because a wrong "yes" there would start agents nobody
asked for. Needs curl and a key in TYPESAFE_API_KEY or OPENROUTER_API_KEY.

Exit: hook is always 0. ask and eval: 0 ok, 1 a case missed or its call failed (eval), 2 the call
could not be made (no key, curl failed, questions.json unreadable), 64 wrong arguments.
"""
import json, os, re, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
BAD_ENV = []  # threshold variables that were set to something that is not a number


def threshold(name, default):
    """A threshold from the environment. A value that is not a number is ignored, so the hook cannot crash on it."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        BAD_ENV.append(name)
        return default


# About 2,000 tokens. A route is decided by what the prompt asks for, which sits at its start;
# a long paste after that adds cost and delay without changing the answer.
MAX_STATE = 8000
# Shorter prompts are replies ("yes", "go on", "use the second one"), not new tasks to route.
MIN_PROMPT = 25
# Seconds curl may take. A call normally returns in under half a second; this must stay below
# the hook timeout in README.md (25) so curl gives up before the host kills the hook.
CURL_SECONDS = 20
# The three thresholds below come from the scores of the 59 labelled cases over three runs;
# evals/jev-judge/README.md has the numbers.
# Process: the one unstable case (h-node-bump) never scored above 0.60, and every other correct
# pick scored 0.80 or more. The lowest of those, fix-didnt-fix, ranged 0.80 to 0.85, so it sits
# on the line and the hook may stay silent on it.
PROCESS_MIN = threshold("JEV_ROUTE_PROCESS_MIN", 0.80)
# Opt-in: real opt-ins scored 0.94 or more and everything else 0.45 or less. The bar sits high
# in that gap because a wrong "yes" starts agents nobody asked for.
OPT_IN_MIN = threshold("JEV_ROUTE_OPT_IN_MIN", 0.85)
# Strong fit: tasks labelled as worth offering a workflow scored 0.99 or more, and tasks labelled
# as not worth one 0.13 or less. One task with no orchestration label (migration-library) scores
# 0.69 to 0.75, either side of the bar; that is tolerable because crossing it only adds an offer.
STRONG_MIN = threshold("JEV_ROUTE_STRONG_MIN", 0.70)

GATES = {
    "incident_response": ("Incident Response", "mitigate before diagnosing; always write the postmortem"),
    "code_review": ("Code Review", "understand the intent before commenting; triage every comment"),
    "debugging": ("Debugging", "reproduce before theorising; keep a written hypothesis log"),
    "bug_fix": ("Bug Fix", "a reliable reproduction, then a failing test, before the fix"),
    "spike": ("Spike / Prototype", "time-box it and throw the code away"),
    "onboarding": ("Onboarding", "one small real contribution early"),
    "dependency_upgrade": ("Dependency Upgrade", "read the full changelog; one major version at a time"),
    "migration": ("Migration", "inventory before estimating; not done until the old path is deleted"),
    "refactor": ("Refactor", "tests cover the area first; one named transform per commit"),
    "feature_implementation": ("Feature Implementation", "the plan is approved before code is written"),
    "tdd_ralph": ("TDD-Ralph loop", "a sandbox and human-written failing tests before the loop runs; ask the user before starting"),
}

# Things that are secrets by their shape. A key prefix counts only when what follows looks like a
# key (it has a digit, or is one long unbroken run), so "ts-node-dev" and "npm_config_registry"
# are left alone.
SECRET = re.compile(
    r"(?i)\b(?:sk[-_]|pk_|gh[pos]_|github_pat_|glpat-|xox[abprs]-|vck_|ts_|hf_|npm_)"
    r"(?:(?=[A-Za-z0-9_\-]*\d)[A-Za-z0-9_\-]{12,}|[A-Za-z0-9]{24,})"
    r"|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_\-]{30,}"
    r"|eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)"
    r"|(?<=://)[^/\s:@]+:[^/\s@]+(?=@)", re.S)
# Things that are secrets by their label: the value after `password=`, `api_key: `, `Authorization:`
# or `Bearer `. The label is kept and only the value goes. A `:` or `=` is required, so the words
# "token", "password" and "authorization" in ordinary prose are not touched.
LABELLED = [
    re.compile(r"(?i)((?:api[_-]?key|token|secret|password|passwd|private[_-]?key)\w*[\"']?\s*[:=]\s*[\"']?)[^\s\"',;]{6,}"),
    re.compile(r"(?i)(\bauthorization\s*[:=]\s*(?:(?:bearer|basic|token)\s+)?)[A-Za-z0-9._~+/=\-]{8,}"),
    re.compile(r"(?i)(\bbearer\s+)(?=[A-Za-z0-9._~+/\-]*\d)[A-Za-z0-9._~+/=\-]{16,}"),
]


class RouteError(Exception):
    """The Jev call could not be made or its answer could not be read. The message is safe to print."""


def redact(text):
    text = SECRET.sub("[redacted]", text)
    for pattern in LABELLED:
        text = pattern.sub(lambda m: m.group(1) + "[redacted]", text)
    return text


def ask(task, context=""):
    """One Jev call. Returns {'process','process_conf','opt_in','fit','fit_conf','strong'} or raises RouteError."""
    key = os.environ.get("TYPESAFE_API_KEY") or os.environ.get("OPENROUTER_API_KEY") or ""
    if not key:
        raise RouteError("no Jev key: set TYPESAFE_API_KEY or OPENROUTER_API_KEY")
    try:
        with open(os.path.join(HERE, "questions.json")) as f:
            questions = json.load(f)
    except (OSError, ValueError) as exc:
        raise RouteError("cannot read questions.json beside this script: %s" % exc)
    base = ("https://openrouter.ai/api" if key.startswith("sk-or-") else
            "https://ai-gateway.vercel.sh/typesafe" if key.startswith("vck_") else "https://api.typesafe.ai")
    state = {"user_message": redact(task)[:MAX_STATE], "context": redact(context or "")[:MAX_STATE]}
    body = json.dumps({"model": os.environ.get("JEV_MODEL", "jev-latest"), "state": state, "questions": questions})
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".json") as f:  # mode 0600; the key goes to curl on stdin
            f.write(body); f.flush()
            p = subprocess.run(["curl", "-q", "-sS", "--fail-with-body", "-m", str(CURL_SECONDS), base + "/v1/systemone",
                                "-H", "Content-Type: application/json", "-H", "@-", "--data-binary", "@" + f.name],
                               input=("Authorization: Bearer " + key).encode(), capture_output=True)
    except OSError as exc:
        raise RouteError("cannot run curl: %s" % exc)
    if p.returncode != 0:
        why = (p.stderr.decode(errors="replace").strip().splitlines() or [""])[0][:200]
        raise RouteError("jev call failed (curl exit %d): %s" % (p.returncode, why))
    try:
        a = json.loads(p.stdout)["answers"]
        probs = a["fit"].get("probabilities", {})
        return {"process": a["process"]["choice"], "process_conf": a["process"]["confidence"],
                "opt_in": a["opt_in"]["noul"], "fit": a["fit"]["score"], "fit_conf": a["fit"]["confidence"],
                "strong": float(probs.get("2", 0.0))}
    except (ValueError, KeyError, TypeError, AttributeError):
        raise RouteError("jev answered in a shape this script does not know")


def verdict(route):
    """The orchestration judge's three-way verdict, derived in code from two Jev answers."""
    if route["opt_in"] >= OPT_IN_MIN:
        return "run_workflow"
    if route["strong"] >= STRONG_MIN:
        return "offer_workflow"
    return "no_workflow"


def suggestion(route):
    """Text for the agent, or '' when there is nothing confident to say."""
    lines = []
    if route["process"] in GATES and route["process_conf"] >= PROCESS_MIN:
        name, gate = GATES[route["process"]]
        lines.append("Process: %s. Gate: %s." % (name, gate))
    if route["strong"] >= STRONG_MIN:
        lines.append("Orchestration: this looks like a strong fit for a multi-agent workflow. Running one needs the "
                     "user's own opt-in; if they have not asked for one, offer it with a rough agent count.")
    if not lines:
        return ""
    return ("Suggested workflow route (a fast classifier's guess from the prompt alone; overrule it if the task "
            "says otherwise, and load the workflow-router skill for the steps):\n- " + "\n- ".join(lines))


def run_eval(path, kind):
    """Score a case file. 0 when every case matched, 1 when one missed or its call failed, 2 when the file is unusable."""
    try:
        with open(path) as f:
            cases = [json.loads(line) for line in f if line.strip()]
    except (OSError, ValueError) as exc:
        print("error: cannot read cases from %s: %s" % (path, exc), file=sys.stderr)
        return 2
    ok = errors = 0
    for c in cases:
        try:
            r = ask(c["task"], c.get("context", ""))
        except RouteError as exc:
            errors += 1
            print("ERROR %s %s" % (c.get("id", "?"), exc))
            continue
        got = r["process"] if kind == "process" else verdict(r)
        ok += got == c["expect"]
        print("%s %s expect=%s got=%s process_conf=%.2f opt_in=%.2f fit=%.2f strong=%.2f" % (
            "ok" if got == c["expect"] else "MISS", c["id"], c["expect"], got,
            r["process_conf"], r["opt_in"], r["fit"], r["strong"]))
    print("%d/%d%s" % (ok, len(cases), " (%d calls failed)" % errors if errors else ""))
    return 0 if ok == len(cases) else 1


def main(argv):
    mode = argv[1] if len(argv) > 1 else ""
    if mode == "hook":
        try:  # a hook must never get in the way: any failure is silence
            prompt = (json.load(sys.stdin).get("prompt") or "").strip()
            if len(prompt) < MIN_PROMPT or prompt.startswith("/"):
                return 0
            text = suggestion(ask(prompt))
            if text:
                print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                                         "additionalContext": text}}))
        except Exception:
            pass
        return 0
    for name in BAD_ENV:
        print("warning: %s is not a number; using the default" % name, file=sys.stderr)
    if mode == "ask" and len(argv) in (3, 4):
        try:
            r = ask(argv[2], argv[3] if len(argv) > 3 else "")
        except RouteError as exc:
            print("error: %s" % exc, file=sys.stderr)
            return 2
        r["verdict"] = verdict(r)
        print(json.dumps(r))
        return 0
    if mode == "eval" and len(argv) == 4 and argv[3] in ("process", "orchestration"):
        if not (os.environ.get("TYPESAFE_API_KEY") or os.environ.get("OPENROUTER_API_KEY")):
            print("error: no Jev key: set TYPESAFE_API_KEY or OPENROUTER_API_KEY", file=sys.stderr)
            return 2
        return run_eval(argv[2], argv[3])
    print(__doc__, file=sys.stderr)
    return 64


if __name__ == "__main__":
    sys.exit(main(sys.argv))
