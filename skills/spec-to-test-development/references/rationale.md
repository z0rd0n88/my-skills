# Rationale: why the skill is shaped this way

For people changing this skill. Nothing here is an instruction for a run. Each entry gives the
reason behind one of the skill's rules.

The four rules carry the benefit. Drop one and this is ordinary test-after coding with extra
sessions.

- **Main session only.** The main session holds the request, and it is the one that launches the
  fresh sessions. A subagent either cannot launch fresh sessions, and would write the tests in
  the session that writes the code, or launches them one level further from the user, where
  nobody can answer a blocking question.
- **User-invoked only.** The skill commits and launches other sessions, so starting it is the
  user's decision.
- **Independence.** Tests written by the session that writes the code share its misreadings and
  pass for the wrong reason.
- **The spec is the only channel.** Tests are written before the code exists, and both sides
  must agree on names and signatures without talking. That is why the spec pins the public
  interface exactly.
- **Red before green.** A test that already passes proves nothing about the change, and for a
  bug it means the test encodes the bug instead of catching it.
- **Frozen tests.** Weakening the test is always the cheapest way to green.
- **No spec or tests written in the main session.** That removes the independence the skill
  exists for.
- **Clean tree before starting.** The run commits, and it must not sweep unrelated work into its
  commits.
