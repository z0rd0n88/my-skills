#!/usr/bin/env python3
"""Mechanical helpers for skill-sheriff-cc. Measures and fetches; never judges.

  sheriff.py fetch   <workdir> [extra-url ...]  save the official docs to <workdir>/docs/
  sheriff.py measure <skill-dir>                print facts about a skill as JSON
  sheriff.py quotes  <workdir> <report.md|->    check every quoted line exists in the docs

No rule or limit lives in this file: the limits come from the docs fetched each run.
"""
import json, os, re, sys, urllib.request

CORE = [  # entry points; the content itself is fetched fresh every run
    "https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices.md",
    "https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview.md",
    "https://code.claude.com/docs/en/skills.md",
]
INDEXES = ["https://platform.claude.com/llms.txt", "https://code.claude.com/docs/llms.txt"]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "skill-sheriff-cc"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def slug(url):
    return re.sub(r"[^a-z0-9]+", "-", url.split("://", 1)[1].lower()).strip("-")[:120] + ".md"


def fetch(workdir, extra):
    docs = os.path.join(workdir, "docs")
    os.makedirs(docs, exist_ok=True)
    failed = []
    for url in CORE + extra:
        try:
            text = get(url)
            with open(os.path.join(docs, slug(url)), "w") as f:
                f.write(f"SOURCE: {url}\n\n{text}")
            print(f"saved  {url}  ({len(text)} chars)")
        except Exception as e:
            failed.append(url)
            print(f"FAILED {url}: {e}")
    print("\nOther skill pages listed in the official indexes (API reference pages omitted):")
    seen = set(CORE + extra)
    for idx in INDEXES:
        try:
            for line in get(idx).splitlines():
                m = re.search(r"\((https?://[^)]+\.md)\)", line)
                if m and re.search(r"skill", line, re.I) and "/api/" not in m.group(1) \
                        and m.group(1) not in seen:
                    seen.add(m.group(1))
                    print("  " + line.strip()[:200])
        except Exception as e:
            print(f"  index FAILED {idx}: {e}")
    if failed:
        sys.exit(f"\n{len(failed)} page(s) failed. Do not evaluate from memory.")


def frontmatter(text):
    if not text.startswith("---\n"):
        return None, text, 0
    end = text.find("\n---", 4)
    if end < 0:
        return None, text, 0
    raw, body = text[4:end], text[end + 4:].lstrip("\n")
    try:
        import yaml
        fm = yaml.safe_load(raw) or {}
    except ImportError:  # ponytail: flat key: value only; install PyYAML for nested fields
        fm = dict(l.split(":", 1) for l in raw.splitlines() if ":" in l and not l.startswith(" "))
        fm = {k.strip(): v.strip().strip("\"'") for k, v in fm.items()}
    except Exception as e:
        fm = {"_yaml_error": str(e)}
    return fm, body, raw.count("\n") + 3


LINK = re.compile(r"\]\(([^)#\s]+)[^)]*\)|`([\w./-]+\.(?:md|py|sh|js|ts|json|txt))`")


def links(path):
    text = open(path, errors="replace").read()
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        for a, b in LINK.findall(line):
            t = a or b
            if "://" not in t and not t.startswith("/"):
                out.append((i, t))
    return out


def measure(skill):
    p = os.path.join(skill, "SKILL.md")
    text = open(p).read()
    fm, body, offset = frontmatter(text)
    fm = fm or {}
    desc, wtu = str(fm.get("description", "")), str(fm.get("when_to_use", ""))
    name = str(fm.get("name", ""))
    refs = []
    for line, t in links(p):
        full = os.path.normpath(os.path.join(skill, t))
        r = {"skill_md_line": line, "target": t, "exists": os.path.exists(full)}
        if r["exists"] and full.endswith(".md"):
            r["links_onward_to"] = [x for _, x in links(full)]
        refs.append(r)
    files = sorted(os.path.relpath(os.path.join(d, f), skill)
                   for d, _, fs in os.walk(skill) for f in fs)
    print(json.dumps({
        "dir_name": os.path.basename(os.path.abspath(skill)),
        "frontmatter_starts_line_1": text.startswith("---\n"),
        "frontmatter_fields": list(fm),
        "name": name, "name_chars": len(name),
        "name_chars_outside_a-z0-9-": sorted(set(re.sub(r"[a-z0-9-]", "", name))),
        "description": desc, "description_chars": len(desc),
        "when_to_use_chars": len(wtu), "description_plus_when_to_use_chars": len(desc) + len(wtu),
        "xml_like_tags_in_frontmatter": re.findall(r"<[^>]+>", desc + wtu + name),
        "body_lines": len(body.splitlines()), "body_first_line_number": offset,
        "body_words": len(body.split()),
        "references_from_SKILL_md": refs,
        "files": files,
        "scripts_not_executable": [f for f in files if f.endswith((".py", ".sh"))
                                   and not os.access(os.path.join(skill, f), os.X_OK)],
        "backslash_paths": re.findall(r"\b\w+\\\w+\.\w+", body),
    }, indent=2))


def norm(s):
    s = s.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    s = re.sub(r"[*_`\\]|\[|\]\([^)]*\)", "", s)  # drop markdown emphasis, code ticks, link targets
    return re.sub(r"\s+", " ", s).strip().lower()


URL = re.compile(r"https?://[^\s)§]+")


def quotes(workdir, report):
    """Each `> "quote"` line must name its source URL (same line, or the next line)
    and the quote must appear on that fetched page."""
    docs = os.path.join(workdir, "docs")
    pages = {}
    for f in os.listdir(docs):
        text = open(os.path.join(docs, f)).read()
        pages[text.split("\n", 1)[0].removeprefix("SOURCE: ").strip()] = norm(text)
    lines = (sys.stdin if report == "-" else open(report)).read().splitlines()
    found = bad = 0
    for i, line in enumerate(lines):
        m = re.match(r"^\s*>\s*\"(.*)\"", line)  # greedy: inner quotes stay in the quote
        if not m:
            continue
        q = m.group(1)
        rest = line[m.end():] + " " + (lines[i + 1] if i + 1 < len(lines) else "")
        u = URL.search(rest)
        url = u.group(0).split("#")[0].rstrip(".,") if u else None
        page = pages.get(url) or pages.get((url or "") + ".md")
        if not url:
            problem = "no source URL on this line or the next"
        elif page is None:
            problem = f"cited page was not fetched: {url}"
        elif norm(q) not in page:
            problem = f"not on the cited page {url}"
        else:
            found += 1
            continue
        bad += 1
        print(f"FAIL line {i + 1}: \"{q[:100]}\" — {problem}")
    print(f"{found} quote(s) verified on their cited page, {bad} failed")
    if bad or not found:
        sys.exit(1)


if __name__ == "__main__":
    cmd, args = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else ("", [])
    if cmd == "fetch" and args:
        fetch(args[0], args[1:])
    elif cmd == "measure" and len(args) == 1:
        measure(args[0])
    elif cmd == "quotes" and len(args) == 2:
        quotes(*args)
    else:
        sys.exit(__doc__)
