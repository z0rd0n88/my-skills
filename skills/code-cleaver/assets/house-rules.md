1. WRITE SCOPE. Edit only the plan and checklist.md. A fix that belongs in any other file
   is ruled on normally and reported open with its proposed text. No commit, stage or push.
2. DECIDED BY THE OWNER. <answer 1>. <answer 2>. <answer 3>. Reproduce these. A finding one
   of them resolves is fix-here; a finding that wants a different answer is
   real-but-decided-elsewhere, owner: the repo owner.
3. OWNER DECISIONS. A finding that needs a decision the three answers do not cover adds one
   bullet to the plan's Open questions and decides nothing.
4. GROUND TRUTH. Read repo state from the audit worktree at <SHA>, and only from there.
5. MEASURED NUMBERS. A number written into the plan comes from a command run and quoted in
   the verdict. If it cannot be measured, the fix removes or qualifies the claim.
6. SHORT PLAN. Rewrite the wrong sentence or cell in place, so the plan keeps its sections
   and its length. State each rule once. Lens wording lives in checklist.md only.
7. SLICE MODEL. Slices by area, seven lenses, one report, at most two fix PRs, one or two
   directories per run. A finding may correct this model; the model itself stays.
