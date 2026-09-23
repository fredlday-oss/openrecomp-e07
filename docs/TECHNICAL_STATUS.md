# OpenRecomp Technical Status

This page is a concise, evidence-oriented view of what OpenRecomp currently demonstrates and what remains research work. It is not a compatibility list and does not imply support for arbitrary commercial software.

## Evidence vocabulary

- **PROVEN** — supported by the stated reproducible evidence for the bounded claim.
- **BOUNDED** — demonstrated within explicitly stated fixtures, architectures or environments.
- **CANDIDATE** — technically plausible or partially demonstrated, but additional validation is required.
- **NOT PROVEN** — the available evidence is insufficient to make the claim.

A PASS on a stage or gate proves only that gate's stated contract. It does not automatically promote a broader compatibility claim.

## Current capability matrix

| Capability | Current status | Boundary |
| --- | --- | --- |
| Architecture-neutral open-core pipeline | **BOUNDED / demonstrated** | Multiple clean guest paths cross shared IR/module/runtime boundaries; arbitrary binaries are not claimed. |
| RV32I validation path | **PROVEN for published bounded fixtures** | Includes hardened ingestion, translation, reference execution and reproducibility evidence. |
| MIPS32 path | **BOUNDED / expanding** | Multi-fixture and real-ELF research exists; general MIPS32 compatibility is not claimed. |
| Normalized IR V1 | **FROZEN-FOR-IMPLEMENTATION** | Versioned public contract used by the current bounded paths. |
| Portable native AOT generation | **BOUNDED / demonstrated** | Native compilation is validated for published fixtures; this is not an arbitrary-binary compiler claim. |
| Native AOT ABI V1 | **FROZEN-FOR-PORTABILITY-TESTING** | Validated on the documented Linux and Windows x64 paths. |
| Deterministic validation and evidence | **PROVEN for published gates** | Repeatable gates, integrity hashes and explicit classifications are part of the engineering model. |
| Explicit host/runtime services | **BOUNDED / demonstrated** | Runtime integration is separated from guest translation and exposed through versioned/typed boundaries. |
| Unreal Engine interoperability | **BOUNDED local/runtime + hosted source gates** | Optional integration only; Unreal is not a core dependency. |
| PlayStation-era (PS1) research | **ACTIVE / NOT PROVEN for general compatibility** | Bounded static-recompilation and compatibility research using legally obtained software. No general PS1 compatibility or commercial-title playability claim is made unless separately evidenced. |
| General legacy-game compatibility | **NOT PROVEN** | OpenRecomp remains a research/developer framework rather than a production universal recompiler. |

## What the pipeline is intended to establish

For an authorised binary, OpenRecomp's engineering workflow can investigate:

1. executable ingestion and structural validation;
2. architecture-specific decoding;
3. code/data and control-flow recovery;
4. reachable-semantics and unresolved-frontier classification;
5. translation into reusable intermediate/module boundaries;
6. native ahead-of-time code generation where supported;
7. explicit runtime/host-service integration;
8. deterministic comparison, replay and evidence capture.

The important property is that unsupported behaviour is classified rather than silently treated as working.

## PlayStation-era research boundary

OpenRecomp is actively developing a bounded PS1 static-recompilation path. This work is intended to exercise the same evidence-first methodology against more realistic legacy software: executable structure, MIPS-family code, indirect control flow, runtime services, graphics/audio/input boundaries and eventual native execution.

Public documentation must distinguish progress on individual gates from broader claims. Until evidence explicitly demonstrates otherwise:

- general PS1 compatibility is **NOT PROVEN**;
- complete commercial-title playability is **NOT PROVEN**;
- compatibility with an individual title must be described only at the level actually established by its evidence;
- no Sony or PlayStation affiliation, endorsement or licensing is implied.

## Commercial evaluation relevance

The same evidence model underpins the [Commercial Evaluation Pilot](../COMMERCIAL_PILOT.md). A commercial evaluation is therefore useful even when a target does not reach native playability: the output can identify the exact compatibility frontier and the engineering work required to move it forward.

## Deeper evidence

See [PROOF_STATUS.md](PROOF_STATUS.md), [ARCHITECTURE.md](ARCHITECTURE.md), [EXTERNAL_REPRO_V1.md](EXTERNAL_REPRO_V1.md), and the repository's tracked evidence/gate material for the exact bounded claims.