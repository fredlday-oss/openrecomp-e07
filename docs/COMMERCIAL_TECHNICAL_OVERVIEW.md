# Commercial Technical Overview

This document explains the technical shape of an OpenRecomp Commercial Evaluation Pilot. It supplements the public [Commercial Evaluation Pilot](../COMMERCIAL_PILOT.md) description; it does not promise a completed port or compatibility outcome.

## Input

A customer provides, under agreed authority and confidentiality terms, a legacy executable or other specifically scoped binary material that it owns or is authorised to provide.

Proprietary material does not need to be committed to the public OpenRecomp repository.

## Evaluation pipeline

Depending on architecture and scope, an evaluation may investigate:

```text
authorised binary
      ↓
format / architecture validation
      ↓
code + data mapping
      ↓
instruction decode
      ↓
control-flow and reachability recovery
      ↓
semantics / unresolved-frontier classification
      ↓
OpenRecomp translation boundary
      ↓
native AOT feasibility
      ↓
runtime + host-service requirements
      ↓
deterministic validation / evidence
```

Not every target will reach every stage. Stopping at a rigorously identified blocker is a valid evaluation result.

## Technical outputs

A scoped engagement can produce:

- executable and architecture assessment;
- recovered/known control-flow and reachability information;
- supported and unresolved semantic inventory;
- runtime/platform dependency inventory;
- reproducible gate results and integrity hashes where applicable;
- compatibility-frontier report;
- native recompilation demonstrator where technically achieved within scope;
- recommended engineering path for a subsequent porting or modernisation project.

## Evidence boundary

OpenRecomp distinguishes **PROVEN**, **BOUNDED**, **CANDIDATE** and **NOT PROVEN** results. A target does not need to become playable for the pilot to produce useful technical evidence.

Commercial schedules or expectations do not change evidence classifications.

## Rights and isolation

Customer binaries, assets, symbols and proprietary documentation remain customer material. They should be kept outside the public repository unless the customer explicitly authorises publication and the material can lawfully be distributed.

OpenRecomp's pre-existing open-source framework remains separate from customer proprietary content.

## Suitable targets

The pilot is intended for organisations investigating legacy software preservation, native platform migration, technical archaeology or modern ports, particularly where historical source/build environments are missing or incomplete.

Suitability depends on architecture, executable format, middleware/dependencies, target outcome and the current OpenRecomp compatibility frontier.

## Before transferring binaries

Initial qualification should establish ownership/authority, original platform and architecture, available materials, desired host target, confidentiality requirements and project scope. Proprietary binaries are not required for the first qualification conversation.

See [TECHNICAL_STATUS.md](TECHNICAL_STATUS.md), [EVIDENCE_MODEL.md](EVIDENCE_MODEL.md) and [../COMMERCIAL_PILOT.md](../COMMERCIAL_PILOT.md).