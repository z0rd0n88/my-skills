---
name: three-agent-wf
description: >-
  3-agent workflow coordinating Claude Code, Codex, and Google Antigravity. Use when
  orchestrating multi-agent tasks, large-scale refactors, or formal verification pipelines.
---

# 3-Agent Workflow Specification: Claude Code, Codex & Antigravity

**Exported:** September 9, 2026

## 1. High-Precision Tool Architecture

To achieve maximum accuracy and precision for platforms like CypherVex (real-time threat detection and reverse proxy evaluation) and Vista, separate inline generation from codebase-wide orchestration and formal verification.

| Tool | Role in Workflow | Key Feature to Leverage |
| :--- | :--- | :--- |
| **Codex** | Tactical, inline code generation | Real-time IDE autocompletion for rapid micro-tasks and boilerplate. |
| **Claude Code** | Dynamic orchestration and codebase-wide changes | Dynamic Workflows (`ultracode` setting) for parallel subagent execution. |
| **Google Antigravity** | Execution environment and absolute verification | Formal verification steps and deterministic tool pipelines to guarantee logic. |

### Lifecycle Execution Sequence

1. **Architecture & Planning (Claude Code)**:
   - Run Claude Code in the terminal using the Explore → Plan methodology.
   - Map existing behavioral heuristics and data flow before authoring code.
   - Establish architectural blueprints and set exact feature boundaries.

2. **Tactical Implementation (Codex)**:
   - Rely on Codex within the IDE for line-by-line autocompletion.
   - Use for deterministic function generation and boilerplate to maintain coding velocity.

3. **Large-Scale Refactoring & Implementation (Claude Code)**:
   - For sweeping modifications (e.g., scoring models or component refactors), trigger Claude Code dynamic workflows with `ultracode`.
   - Parallel subagents handle code authoring while adversarial review agents independently validate the logic.

4. **Formal Verification & Deployment (Google Antigravity)**:
   - Deploy the codebase into Google Antigravity.
   - Route code through formal verification steps to mathematically prove correctness before merging.
   - Leverage deterministic pipelines and rate-limit guardrails.

---

## 2. Deterministic Tool Pipelines in Google Antigravity

Enforcing strict validation gates strips agent autonomy over the runtime environment:

* **Lock Down Execution Policies**: Set Terminal Execution to Off so the agent can only run commands explicitly defined in your allowlist. Pair this with the Request Review policy (or Review-driven development mode) to require human approval.
* **Require Explicit Task Plans**: Force the agent to output a structured Task List & Plan prior to code generation. Review and approve this blueprint to govern the execution path.
* **Mandate Verification Artifacts**: Configure pipelines to produce standardized Code Diffs, before/after UI Screenshots, and Browser Recordings to trace API payloads and execution steps without manual intervention.
* **Enable AI Debugging and Testing**: Activate Antigravity's real-time testing engine. Post-build browser simulations evaluate API contracts and UI states against the task plan, automatically spawning parallel repair subagents if failures occur.

---

## 3. Operational Checklist for Antigravity

When this workflow is active in Antigravity:

1. **Gate on Task Plan**: Output a structured task plan and explicit verification criteria before modifying any tracked files.
2. **Deterministic Tool Execution**: Restrict command execution to project-specific build and test commands (e.g., test suites, linters, and type checkers).
3. **Produce Verification Artifacts**:
   - Save test results and build logs.
   - Provide explicit file diffs showing changes made.
   - If frontend/UI flows are affected, capture visual state or recording evidence.
4. **Handoff Coordination**:
   - Write handoff summaries to persistent markdown artifacts so Claude Code or Codex sessions can ingest state without context degradation.
