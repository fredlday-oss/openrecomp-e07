# OPENRECOMP Phase 1 — P1-99 Evidence (Final Verdict)

Stage: `P1-99` — final Phase-1 verdict

Revision: working tree at HEAD `bd5f02f` (no commit created).

## Verdict

```
OPENRECOMP_PHASE1_MULTIARCH_PROOF=PASS
```

This verdict is used exactly as required by `.openrecomp-phase1/SCOPE.md` and is
justified only by the rules below.

## SCOPE.md coverage (every required item → PASS stage with evidence)

Shared/core completion:

| Requirement | Covered by |
| --- | --- |
| architecture-neutral frontend contract | P1-01 (contract), P1-02, P1-03 |
| architecture-neutral decoded-instruction representation / boundary | P1-01, P1-03, per-arch decoders |
| architecture-neutral CFG/basic-block handoff | P1-01, P1-03, per-arch frontends |
| architecture-neutral IR/lowering handoff | P1-01, P1-03, per-arch lowering gates |
| deterministic architecture test harness | P1-03 |
| existing PS2/R5900 regression behavior preserved | P1-90 (RV32I/E07 + MIPS32 gates green; no PS2 code in-tree) |
| fail-closed unsupported-instruction handling | P1-11/12/20/21/30/31 and platform gates |

Game Boy / Game Boy Color:

| Requirement | Covered by |
| --- | --- |
| SM83 register/flag model | P1-10 |
| complete documented base and CB-prefixed decode | P1-11 |
| verified documented instruction semantics | P1-12 |
| branches/calls/returns/interrupt control-flow classification | P1-13 |
| IR/lowering integration | P1-13 |
| ROM ingestion + memory-map contract | P1-14 |
| no-MBC baseline + clean mapper interface (+ bounded MBC1) | P1-14 |
| timer/interrupt/joypad contracts for deterministic headless tests | P1-15 |
| GB vs GBC platform-mode selection | P1-16 |
| synthetic deterministic CPU/platform trace proof | P1-15, P1-16 |
| regression + differential audit | P1-17 |

Master System:

| Requirement | Covered by |
| --- | --- |
| Z80 architectural frontend | P1-20 |
| documented decoding/semantics required by the test corpus | P1-20, P1-21 |
| interrupt/control-flow integration | P1-21 |
| ROM ingestion | P1-22 |
| baseline Sega banking/memory contract | P1-22 |
| I/O/VDP port abstraction for deterministic tests | P1-22 |
| synthetic/open test proof | P1-23 |
| regression + differential audit | P1-24 |

NES:

| Requirement | Covered by |
| --- | --- |
| 6502-family frontend matching the NES CPU's documented behavior | P1-30, P1-31 |
| documented official opcode semantics required for proof | P1-31 |
| interrupt/reset/NMI control-flow integration | P1-31 (entry mechanics), P1-34 (vector proof) |
| iNES / NES 2.0 ingestion boundary | P1-32 |
| NROM/Mapper 0 baseline + mapper interface | P1-32 |
| CPU-facing PPU/APU/controller register contracts | P1-33 |
| synthetic/open test proof | P1-34 |
| regression + differential audit | P1-35 |

## Final regression confirmation (P1-90)

```text
python tools/phase1_host_gates_v1.py   (full harness, run twice)
RUN1 EXIT=0 TIME=00:06:23.8981181  RUN2 EXIT=0 TIME=00:06:21.1210213
OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
RUN1/RUN2 SHA256=3fbb23d3d0174a7efe381d70a1636987c4355e5b9837d67c8dcb3e158a67f594
OPENRECOMP_P1_90_HARNESS_DETERMINISM=PASS
OPENRECOMP_P1_90_NO_RUN2_SIDE_EFFECTS=PASS
```

The architecture-boundary audit (P1-90) confirms the Core API and IR remain
architecture-neutral, each guest CPU model is separate from its platform layer,
unsupported behavior fails closed, and no commercial ROM bytes entered the
repository. The two skipped gates are the unchanged toolchain-gated
`e07-hardened-end-to-end` and `external-repro-v1` gates (no `clang`/`gcc`/POSIX
on this host); a skip is never counted as a pass.

## Non-claims

Per SCOPE.md this is **not** a claim of cycle-perfect or universal
commercial-game compatibility. The consolidated limitations and fail-closed
boundaries are recorded in `.openrecomp-phase1/evidence/INDEX.md`.

## Verdict line

```
OPENRECOMP_PHASE1_MULTIARCH_PROOF=PASS
```
