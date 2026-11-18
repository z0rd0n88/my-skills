#!/bin/bash
# Self-check for block-dangerous-git.sh. Run: bash test-block-dangerous-git.sh [path-to-script]
# With no argument it tests the bundled copy next to this file.
HOOK="${1:-$(dirname "$0")/block-dangerous-git.sh}"
fail=0
json() { python3 -c 'import json,sys; print(json.dumps({"tool_input": {"command": sys.argv[1]}}))' "$1"; }
check() { # expected-exit command
  json "$2" | bash "$HOOK" 2>/dev/null
  got=$?
  [ "$got" = "$1" ] || { echo "FAIL (want $1, got $got): $2"; fail=1; }
}

BLOCK=(
  "git push origin main" "git  push" "git -C /tmp/repo push" "git -c core.x=y push"
  "git --no-pager push --force-with-lease" "cd x && git push" "git reset --hard HEAD~1"
  "git reset HEAD --hard" "git clean -f" "git clean -xdf" "git clean --force" "git clean"
  "git branch -D feat" "git branch --delete --force feat" "git checkout ." "git checkout -- ."
  "git restore ." "git --git-dir=.git reset --hard"
  # separators
  "git clean -fd;ls" "git checkout .&&true" "(git restore .)" "git branch -D x|cat" "git restore .|x"
  # abbreviations, split and bundled flags
  "git reset --har" "git reset --ha HEAD" "git branch -d -f x" "git branch -df x" "git branch --del --fo x"
  # quoting, continuations, wrappers, substitutions
  "git 'push'" "\"git\" push" $'git \\\npush' "/usr/bin/git push" "env FOO=1 git push"
  "sh -c 'git push'" "bash -lc \"git reset --hard\"" "eval git push" 'echo `git push`'
  'echo $(git reset --hard)' "git commit -m 'unbalanced"
  # git-free forms
  "g push --force" "g reset --hard"
  "$(printf 'echo %.0s' {1..20000}) ; git push"
)
ALLOW=(
  "git status" "git log --oneline" "git branch -d feat" "git clean -n" "git clean --dry-run -fd"
  "git checkout main" "git checkout ./src/file.ts" "git checkout .gitignore"
  "git restore --staged src/a.ts" "git reset --soft HEAD~1" "git log --grep push"
  "git commit -m \"fix: don't git push yet\"" "grep -r 'git push' docs" "echo pushd" "ls -la"
)
for c in "${BLOCK[@]}"; do check 2 "$c"; done
for c in "${ALLOW[@]}"; do check 0 "$c"; done

# Fail closed: unparsable input and an empty command are blocked.
echo 'not json' | bash "$HOOK" 2>/dev/null; [ $? = 2 ] || { echo "FAIL: bad JSON not blocked"; fail=1; }
echo '{}' | bash "$HOOK" 2>/dev/null; [ $? = 2 ] || { echo "FAIL: missing command not blocked"; fail=1; }

[ $fail = 0 ] && echo "all checks pass (${#BLOCK[@]} blocked, ${#ALLOW[@]} allowed)"
exit $fail
