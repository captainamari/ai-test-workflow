---
name: ai-test-workflow
description: Build reviewable business rules and executable test plans from requirements, API contracts, domain knowledge and existing tests. Use for staged test generation or diagnosing a failed generated case in the companion Python workflow project.
---

# AI test workflow

Work from the companion project root containing `workflow.py`. The user supplies a run directory. Keep other runs and company repositories unchanged unless the task explicitly includes them.

Read that run's `inputs/requirements.md`, `contract.json`, `domain.md`, `capabilities.json` and `existing_test.py`. Use [formats.md](references/formats.md) for artifact structure and workflow commands.

Choose the stage that matches the request:

- Requirements to rules: read [01-spec.md](references/01-spec.md), write `spec.json`, run `check --stage spec`, and present unresolved questions and rules for business review.
- Reviewed rules to cases: verify that `review-spec.json` matches the current inputs and spec, read [02-cases.md](references/02-cases.md), write `cases.json`, run `check --stage cases`, and present the test plan for review.
- Reviewed cases to code and results: use `workflow.py render` then `workflow.py run`. Use [03-diagnose.md](references/03-diagnose.md) to explain failures. Do not rewrite a failing expectation to match observed behavior.
- Company framework migration: read [04-adapt.md](references/04-adapt.md). Map real capabilities before implementing an adapter or changing the case schema.

Only repair artifacts belonging to the current stage. Reuse rule and case IDs when their meaning is unchanged. If a source conflicts with another source, retain the conflict as an open question instead of selecting the convenient answer. Missing execution or observation capabilities keep the affected case blocked.

The `approve` command records a review decision; do not issue it on a person's behalf unless that person explicitly confirmed the current artifact. A matching hash proves version association, not the identity or quality of the reviewer. The bundled `demo` is a reference replay and deliberately labels its review records as non-human examples.

For a check failure, make at most two targeted repair attempts using the reported errors. Then return the remaining errors, relevant input excerpts and the blocked artifact. Stop after the requested stage; do not add publishing, company-system calls or unrelated dependency setup.

For a generation-quality evaluation, do not read `examples/reference/` or `demo_service.py` before producing rules and cases. Those files contain answers or implementation behavior and would contaminate the trial. They may be used later to inspect a failed local demonstration, with that use recorded.
