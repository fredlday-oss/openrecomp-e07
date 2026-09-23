# OpenRecomp Phase 2 progress — 14 September 2026

OpenRecomp has moved well into **Phase 2**, following completion of the Phase 1 multi-architecture foundation.

The current working development frontier has reached **P2-09**.

> **Status boundary:** this page reports active development progress. The public `main` branch does not yet contain every Phase 2 change described here, and this update should not be read as a release claim.

## What Phase 2 is doing

Phase 1 established and verified many of the architecture, ingestion, semantics and host-contract foundations needed by OpenRecomp. Phase 2 is connecting those pieces into a more complete static recompilation pipeline.

Work in the Phase 2 sequence has advanced areas including:

- a common program representation for ingested guest binaries;
- control-flow graph recovery;
- function discovery;
- inter-function call graph recovery;
- translation-unit construction;
- host-code emission infrastructure; and
- deterministic validation and evidence generation around the individual stages.

The project continues to develop these capabilities as bounded stages rather than treating the compiler as one large, unverifiable pass. Each stage is intended to have an explicit acceptance boundary, regression coverage and reproducible evidence before the frontier moves on.

## Why this matters

The important shift in Phase 2 is from proving isolated recompilation primitives toward recovering and translating the structure of a complete program.

The pipeline increasingly needs to answer higher-level questions such as:

- What executable code exists?
- How is that code connected by control flow?
- Which functions can be recovered?
- Which functions call other functions?
- How should recovered code be grouped into translation units?
- How can those units be emitted as native host code while retaining deterministic validation?

Those capabilities are essential to OpenRecomp's longer-term objective: taking a legally obtained legacy software binary and producing modern native code without requiring the original source code.

## Rights-safe development

Public OpenRecomp development continues to use synthetic, generated, homebrew or otherwise clearly redistributable fixtures and evidence.

Commercial game ROMs, proprietary executable content, console firmware, keys and proprietary SDK material are not added to the public repository.

## Current direction

The immediate development path is:

**P2-09 → remaining Phase 2 stages → Phase 2 integration and final verification**

As individual Phase 2 boundaries are completed and prepared for publication, the corresponding implementation and evidence can be merged into the public development history.

OpenRecomp remains an experimental research/developer project. Phase 2 is nevertheless an important transition: the project is moving from individual proven components toward an integrated end-to-end static recompilation path.
