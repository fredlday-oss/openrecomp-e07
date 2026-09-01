# Development process and automated assistance

OpenRecomp uses a human-led development process that may include automated and AI-assisted tools for activities such as code drafting, refactoring, test generation, documentation drafting, repository analysis and review support.

Automated output is not treated as proof by itself. Project claims must be grounded in executable tests, reproducible build results, runtime evidence or explicit manual inspection. A generated suggestion, summary or status label cannot promote a component from `CANDIDATE` to `PASS`, `PROVEN` or another stronger evidence state.

## Maintainer responsibility

The maintainer remains responsible for deciding what is accepted into the repository, reviewing the resulting change, preserving licensing and provenance requirements, and ensuring that the claimed validation actually ran.

Material AI or automated assistance that substantially shapes a pull request should be disclosed in the pull-request description or accompanying development notes. Contributors do not need to list every autocomplete event or mechanical transformation; the purpose is to make significant machine-assisted authorship or review visible rather than infer it from commit velocity.

## Validation policy

Machine-assisted development must not weaken the normal acceptance gates. Relevant changes are expected to retain or add deterministic tests, negative/adversarial cases, compiler/runtime checks and evidence-bound status updates. Independent execution paths are preferred where practical so one generated implementation is not used as its own oracle.

## Rights and source hygiene

Use of automated tools does not change contributor responsibility for source rights. Do not provide or commit proprietary game code, commercial executable content, firmware, keys, credentials, private logs or other material that is not suitable for public redistribution.

When automated tools are used to transform or review third-party material, contributors remain responsible for ensuring the resulting contribution is compatible with the project's license and clean-input policy.

## Evidence provenance

OpenRecomp distinguishes reproducible CI evidence from machine-local runtime evidence. A locally executed result may be useful and may be retained as public-safe evidence, but external-facing status should identify that provenance when the required environment is not available in hosted CI.

The project's status vocabulary and current evidence boundaries are documented in `docs/PROOF_STATUS.md`.
