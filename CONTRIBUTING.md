# Contributing to OpenRecomp

OpenRecomp welcomes changes that improve the reusable static-recompilation framework, validation tooling, documentation, architecture adapters and host integrations.

## Before opening a pull request

Run:

```bash
./RUN.sh
python3 tools/public_safety_scan.py
python3 tools/check_markdown_links.py
```

The hardened E07 proof must continue to pass unless the pull request explicitly changes a proof contract and supplies equivalent reviewed evidence.

## Evidence language

OpenRecomp uses status words deliberately:

- **PROVEN** — directly established by the current reproducible evidence set.
- **PASS** — a bounded validation/test completed successfully.
- **PROVEN-RUNTIME** — expected behavior was validated during runtime execution with an evidence path that is reproducible at the stated scope.
- **CANDIDATE** — an interface or direction exists but has not crossed the required proof gate.

Machine-local runtime observations that cannot currently be reproduced in project-controlled CI should be reported as **PASS — local runtime evidence** with the environment/provenance stated explicitly, rather than as an unqualified `PROVEN-RUNTIME` claim.

Do not promote a component from CANDIDATE to PROVEN without reproducible evidence.

## Automated and AI-assisted development

OpenRecomp uses a human-led process that may include automated and AI-assisted tools for drafting, refactoring, tests, documentation, analysis and review support. See [`DEVELOPMENT_PROCESS.md`](DEVELOPMENT_PROCESS.md).

If automated or AI assistance materially shaped a pull request, disclose that in the pull-request description or accompanying development notes. You do not need to enumerate every autocomplete event; disclose substantial machine-assisted authorship or review so contributors and reviewers do not have to infer it from commit history.

Automated output is never evidence by itself. The maintainer/contributor remains responsible for the change, its licensing/provenance, and the tests or runtime evidence used to justify status claims.

## Clean-input policy

Public tests and examples must be original, synthetic, homebrew, or otherwise clearly redistributable.

Do not submit commercial game binaries/assets, firmware, console keys, proprietary SDK material, credential dumps, authentication logs or copyrighted executable samples.

## Architecture changes

Changes to adapters, IR/schema, runtime contracts, memory behavior or host interfaces should include the affected contract, compatibility impact, deterministic validation, negative/adversarial cases where relevant, and updated documentation.

## Pull requests

Keep changes focused. Explain what changed, why it is safe, what proof status is affected, how you validated it, and whether any material automated/AI assistance was used.
