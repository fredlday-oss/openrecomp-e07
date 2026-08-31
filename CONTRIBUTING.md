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

- **PROVEN** — directly established by the current evidence set.
- **PASS** — a bounded validation/test completed successfully.
- **PROVEN-RUNTIME** — expected behavior was validated during actual runtime execution.
- **CANDIDATE** — an interface or direction exists but has not crossed the required proof gate.

Do not promote a component from CANDIDATE to PROVEN without reproducible evidence.

## Clean-input policy

Public tests and examples must be original, synthetic, homebrew, or otherwise clearly redistributable.

Do not submit commercial game binaries/assets, firmware, console keys, proprietary SDK material, credential dumps, authentication logs or copyrighted executable samples.

## Architecture changes

Changes to adapters, IR/schema, runtime contracts, memory behavior or host interfaces should include the affected contract, compatibility impact, deterministic validation, negative/adversarial cases where relevant, and updated documentation.

## Pull requests

Keep changes focused. Explain what changed, why it is safe, what proof status is affected, and how you validated it.
