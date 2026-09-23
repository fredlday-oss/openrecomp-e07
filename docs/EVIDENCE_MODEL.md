# OpenRecomp Evidence Model

OpenRecomp treats evidence as part of the product rather than an after-the-fact test report. The purpose is to make technical claims reviewable, bounded and reproducible.

## Principles

### Claims are bounded

A passing fixture or stage proves only the contract exercised by that fixture or stage. It does not imply arbitrary binary, architecture, platform or game compatibility.

### Fail closed

Malformed inputs, unsupported semantics, ABI mismatches and unresolved requirements should reject or remain explicitly unresolved rather than silently continuing as though supported.

### Determinism matters

Where a gate claims deterministic output, repeated runs are compared using stable machine-readable records and/or cryptographic hashes. Byte-identical evidence is preferred where the contract permits it.

### Reference and translated execution are separated

Where applicable, OpenRecomp compares translated/native behaviour against an independent or reference execution path. Agreement is reported only for the state and observations included in the gate contract.

### Provenance is recorded

Evidence records can include source/input hashes, toolchain information, output hashes, gate counts and explicit status markers. This makes it possible to distinguish a result from the inputs and environment that produced it.

### Unsupported is a result

An unresolved instruction, indirect target, service, runtime dependency or platform behaviour is a compatibility frontier. Classifying that frontier accurately is preferable to producing a misleading success result.

## Classification vocabulary

**PROVEN** — the stated bounded claim is supported by the required evidence.

**BOUNDED** — the behaviour is demonstrated within stated constraints that matter to interpretation.

**CANDIDATE** — there is technical evidence or implementation progress, but the stronger claim still requires validation.

**NOT PROVEN** — evidence is insufficient for the proposed claim. This is not synonymous with impossible or permanently unsupported.

## Typical evidence flow

```text
input + provenance
       ↓
fail-closed ingestion
       ↓
decode / recovery / translation
       ↓
reference and/or native execution
       ↓
observable-state comparison
       ↓
repeated gate execution
       ↓
machine-readable result + hashes
       ↓
explicit bounded classification
```

## Why this matters commercially

For preservation, migration and porting work, a binary that does not immediately run can still yield useful engineering information. OpenRecomp's Commercial Evaluation Pilot is designed around that fact: the deliverable can be a reproducible compatibility frontier showing what is understood, what is translated, what remains unresolved and what engineering work is likely to be required next.

See [TECHNICAL_STATUS.md](TECHNICAL_STATUS.md), [PROOF_STATUS.md](PROOF_STATUS.md) and [../COMMERCIAL_PILOT.md](../COMMERCIAL_PILOT.md).