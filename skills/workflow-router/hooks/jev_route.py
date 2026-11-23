#!/usr/bin/env python3
"""Route a task with Jev (TypeSafe's System One model): process workflow, and orchestration fit.

  jev_route.py ask  '<task>' [context]     print the route as JSON
  jev_route.py eval <cases.jsonl> process|orchestration   score a case file
  jev_route.py hook                        UserPromptSubmit hook: read the event on stdin, suggest a route

One Jev call answers three questions (questions.json beside this file). The hook only suggests:
it never blocks a prompt, prints nothing when Jev is unsure or unreachable, and never tells the
agent that the user opted in to a workflow, because a wrong "yes" there would start agents nobody
asked for. Needs curl and a key in TYPESAFE_API_KEY or OPENROUTER_API_KEY.
"""
import json, os, re, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
QUESTIONS = json.load(open(os.path.join(HERE, "questions.json")))
MAX_STATE = 8000          # characters of the prompt sent to Jev
MIN_PROMPT = 25           # shorter prompts ("yes", "go on") are not routed
PROCESS_MIN = float(os.environ.get("JEV_ROUTE_PROCESS_MIN", "0.80"))
OPT_IN_MIN = float(os.environ.get("JEV_ROUTE_OPT_IN_MIN", "0.85"))
STRONG_MIN = float(os.environ.get("JEV_ROUTE_STRONG_MIN", "0.70"))

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

SECRET = re.compile(
    r"(?i)\b(?:sk|pk|ghp|gho|ghs|github_pat|glpat|xox[abprs]|vck|ts|hf|npm)[-_][A-Za-z0-9_\-]{12,}"
    r"|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_\-]{30,}"
    r"|eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)"
    r"|(?<=://)[^/\s:@]+:[^/\s@]+(?=@)"
    r"|(?:(?:api[_-]?key|token|secret|password|passwd|authorization|bearer)\s*[:=]?\s*)\S{6,}", re.S)


def redact(text):
    return SECRET.sub("[redacted]", text)


def ask(task, context=""):
    """One Jev call. Returns {'process','process_conf','opt_in','fit','fit_conf','strong'} or raises."""
    key = os.environ.get("TYPESAFE_API_KEY") or os.environ.get("OPENROUTER_API_KEY") or ""
    if not key:
        raise RuntimeError("no Jev key")
    base = ("https://openrouter.ai/api" if key.startswith("sk-or-") else
            "https://ai-gateway.vercel.sh/typesafe" if key.startswith("vck_") else "https://api.typesafe.ai")
    state = {"user_message": redact(task)[:MAX_STATE], "context": redact(context or "")[:MAX_STATE]}
    body = json.dumps({"model": os.environ.get("JEV_MODEL", "jev-latest"), "state": state, "questions": QUESTIONS})
    with tempfile.NamedTemporaryFile("w", suffix=".json") as f:  # mode 0600; the key goes to curl on stdin
        f.write(body); f.flush()
        p = subprocess.run(["curl", "-q", "-sS", "--fail-with-body", "-m", "20", base + "/v1/systemone",
                            "-H", "Content-Type: application/json", "-H", "@-", "--data-binary", "@" + f.name],
                           input=("Authorization: Bearer " + key).encode(), capture_output=True)
    if p.returncode != 0:
        raise RuntimeError("jev call failed (curl exit %d)" % p.returncode)
    a = json.loads(p.stdout)["answers"]
    probs = a["fit"].get("probabilities", {})
    return {"process": a["process"]["choice"], "process_conf": a["process"]["confidence"],
            "opt_in": a["opt_in"]["noul"], "fit": a["fit"]["score"], "fit_conf": a["fit"]["confidence"],
            "strong": float(probs.get("2", 0.0))}


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


def main(argv):
    mode = argv[1] if len(argv) > 1 else ""
    if mode == "ask":
        r = ask(argv[2], argv[3] if len(argv) > 3 else "")
        r["verdict"] = verdict(r)
        print(json.dumps(r)); return 0
    if mode == "eval":
        kind, ok, n = argv[3], 0, 0
        for line in open(argv[2]):
            c = json.loads(line); n += 1
            r = ask(c["task"], c.get("context", ""))
            got = r["process"] if kind == "process" else verdict(r)
            ok += got == c["expect"]
            print("%s %s expect=%s got=%s process_conf=%.2f opt_in=%.2f fit=%.2f strong=%.2f" % (
                "ok" if got == c["expect"] else "MISS", c["id"], c["expect"], got,
                r["process_conf"], r["opt_in"], r["fit"], r["strong"]))
        print("%d/%d" % (ok, n)); return 0
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
    print(__doc__, file=sys.stderr); return 64


if __name__ == "__main__":
    sys.exit(main(sys.argv))
