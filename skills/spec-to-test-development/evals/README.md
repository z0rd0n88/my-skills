# Running these evals

Run each case as the main session of a new session, for example `claude -p "<query>"` started in
an empty working directory, with `<workdir>` replaced by that directory.

Do not run them through a runner that launches one subagent per case. spec-to-test-development refuses to run
inside a subagent, so every case would return `spec-to-test-development must be run from the main session`.
That refusal is correct behaviour, not a failed eval.
