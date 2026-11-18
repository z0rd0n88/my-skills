#!/bin/bash
# Self-check for block-dangerous-git.sh. Run: bash test-block-dangerous-git.sh [path-to-script]
# With no argument it tests the bundled copy next to this file.
HOOK="${1:-$(dirname "$0")/block-dangerous-git.sh}"
fail=0
check() { # expected-exit command
  printf '%s' "$(jq -cn --arg c "$2" '{tool_input:{command:$c}}')" | bash "$HOOK" 2>/dev/null
  got=$?
  [ "$got" = "$1" ] || { echo "FAIL (want $1, got $got): $2"; fail=1; }
}

for c in "git push origin main" "git  push" "git -C /tmp/repo push" "git -c core.x=y push" \
         "git --no-pager push --force-with-lease" "cd x && git push" "git reset --hard HEAD~1" \
         "git reset HEAD --hard" "git clean -f" "git clean -xdf" "git clean --force" \
         "git branch -D feat" "git branch --delete --force feat" "git checkout ." \
         "git checkout -- ." "git restore ." "git --git-dir=.git reset --hard"; do
  check 2 "$c"
done
for c in "git status" "git log --oneline" "git branch -d feat" "git clean -n" \
         "git checkout main" "git checkout ./src/file.ts" "git restore --staged src/a.ts" \
         "git reset --soft HEAD~1" "echo pushd" "ls -la"; do
  check 0 "$c"
done

# Fail closed: unparsable input and an empty command are blocked.
echo 'not json' | bash "$HOOK" 2>/dev/null; [ $? = 2 ] || { echo "FAIL: bad JSON not blocked"; fail=1; }
echo '{}' | bash "$HOOK" 2>/dev/null; [ $? = 2 ] || { echo "FAIL: empty command not blocked"; fail=1; }

[ $fail = 0 ] && echo "all checks pass"
exit $fail
