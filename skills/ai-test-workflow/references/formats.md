# Artifact formats and commands

All paths passed to commands below are relative to the project root. Replace `runs/pilot` with the chosen run directory. Python 3.10+ and the standard library are sufficient. The model is provided by the user's coding assistant; this project does not call or configure a model API.

## Inputs

`inputs/requirements.md` defines desired behavior. `contract.json` defines actual request/response fields and allowed business codes. `domain.md` defines entity/state/consistency assumptions. `capabilities.json` describes executable test preparation, invocation, observation and cleanup methods. `existing_test.py` shows maintained test style. Capability descriptions are not proof of runtime availability.

Create a run with `python workflow.py init runs/pilot`. Replace its example inputs before generation; then run `python workflow.py snapshot runs/pilot`. Changing inputs, spec or cases invalidates dependent review hashes. Re-review before rendering. Never overwrite an old report to hide a failure.

## spec.json

The exact root keys are `rules` (nonempty array) and `open_questions` (array of nonempty strings, or empty).
Each rule has exactly `id`, `statement`, `source`. IDs match `R[0-9]+` and are unique. Source has exactly `file` and `quote`. File is an actual path relative to inputs; quote is an exact excerpt of at least eight characters. A quote match establishes provenance, not semantic correctness.

```json
{"rules":[{"id":"R01","statement":"数量必须为正整数。","source":{"file":"requirements.md","quote":"这里必须替换为输入文件中的原文片段"}}],"open_questions":[]}
```

The quote above illustrates structure, not a valid fixture. Use a real excerpt from the selected input.

## cases.json

Root: exactly `cases`, a nonempty array (maximum 100). Each case has exactly these fields:

| Field | Meaning |
| --- | --- |
| id | Unique `C[0-9]+` |
| title | Specific test intention |
| rule_ids | Nonempty array of existing unique rule IDs |
| status | `ready` or `blocked` |
| blocked_reason | Empty for ready; actual missing fact or capability for blocked |
| initial_stock | Nonnegative integer for ready; null for blocked |
| requests | 1–8 `{quantity, key}` objects for ready; empty for blocked |
| expect | Expected observations for ready; null for blocked |

`quantity` preserves its JSON scalar type and value. `key` matches `[a-z0-9-]{1,32}`; equal keys within a case generate equal request IDs. Distinct cases are isolated by a fresh namespace.

`expect` has exactly `codes` (one allowed code per request), `remaining_stock` (nonnegative integer), `reservation_count` (nonnegative integer), `same_reservation` (true for multiple successful responses expected to share an ID; null otherwise).

Ready cases require all five provided capabilities to be marked available. Blocked cases retain their rule references, but do not count as executed or accepted. Every rule needs at least one planned case; that is not branch-coverage measurement.

The sample schema targets single-item reservations. A new domain requires a corresponding schema, validator, template and adapter. Do not force unrelated operations into inventory fields.

## Commands

```bash
python workflow.py check runs/pilot --stage spec
python workflow.py approve runs/pilot --stage spec --reviewer "reviewer-name"
python workflow.py check runs/pilot --stage cases
python workflow.py approve runs/pilot --stage cases --reviewer "reviewer-name"
python workflow.py render runs/pilot
python workflow.py run runs/pilot
```

Approval commands are performed after the current artifact is actually reviewed. Render writes a new generated directory; old versions remain. Run verifies source, artifact, implementation and generated-file fingerprints before executing. Exit codes: 0 completed successfully; 1 test failure or blocked delivery; 2 invalid input, stale review or setup error.
