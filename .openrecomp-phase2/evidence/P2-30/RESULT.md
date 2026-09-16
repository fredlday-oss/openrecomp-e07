# P2-30 — Cross-Architecture Neutrality Audit

VERDICT: `PASS`

STAGE MARKER: `OPENRECOMP_P2_30=PASS`
GATE MARKER: `OPENRECOMP_CROSS_ARCHITECTURE_NEUTRALITY_V1=PASS tests=14`

## Baseline

| Item | Value |
| --- | --- |
| Stage | `OPENRECOMP_P2_30_CROSS_ARCHITECTURE_NEUTRALITY_V1` |
| Branch | `phase2/opencode-v1` |
| Starting state | `OPENRECOMP_P2_23=PASS`, `OPENRECOMP_NES_END_TO_END_V1=PASS tests=50`, `CURRENT_STAGE=P2-30` |
| Phase-1 freeze | tag `openrecomp-phase1-pass` -> `46c2f971e1a42cf49bd936bad94697b81bf31002` (unchanged) |
| Prior gates | P2-23 `50`, P2-22 `66`, P2-21 `74`, P2-20 `86`, P2-14 `82`, P2-13 `80`, P2-12 `96`, P2-11 `77`, P2-10 `108`, P2-09 `120`, P2-08 `169`, P2-07 `106`, P2-06 `134`, P2-05 `104`, P2-04 `61`, P2-03 `67`, P2-02 `82`, P2-01 `49` |

## Objective

Audit the completed Phase-2 architecture and prove that the shared recompilation
pipeline remains architecture-neutral after the NES6502 integration. Determine
whether architecture-specific assumptions have leaked into generic Phase-2
layers. The shared layers must remain usable by other guest architectures such
as MIPS32/R5900 and future architectures without requiring NES-specific behavior
in architecture-neutral code.

## Audit scope

Inspected shared Phase-2 implementation modules:

| Module | Stage | Responsibility |
| --- | --- | --- |
| `openrecomp/program_model.py` | P2-01 | Persistent program representation, decoded-instruction abstractions |
| `openrecomp/cfg.py` | P2-02 | CFG construction, basic-block recovery |
| `openrecomp/functions.py` | P2-03 | Function discovery |
| `openrecomp/call_graph.py` | P2-04 | Direct call-graph recovery |
| `openrecomp/translation_units.py` | P2-05 | Translation-unit generation |
| `openrecomp/indirect_control_flow.py` | P2-06 | Indirect-control-flow classification |
| `openrecomp/host_emitter.py` | P2-07 | Host emitter |
| `openrecomp/runtime_abi.py` | P2-08 | Generic runtime ABI |
| `openrecomp/build_pipeline.py` | P2-09 | Deterministic build pipeline |

Inspected architecture-specific boundary modules:

| Module | Stage | Responsibility |
| --- | --- | --- |
| `openrecomp/frontends/nes6502.py` | P2-20 | NES6502 program bridge |
| `openrecomp/frontends/nes_runtime.py` | P2-22 | NES runtime adapter |

Also reviewed: `openrecomp/frontends/__init__.py`, `openrecomp/frontends/scaffold.py`.

## Method

The audit gate `tools/test_cross_architecture_neutrality_v1.py` performs:

1. **Static import isolation**: parse the AST of every shared module and verify
   it does not import from `adapters.*`, `adapters.nes6502`, `adapters.mips32`,
   `openrecomp.frontends.nes6502`, `openrecomp.frontends.nes_runtime`, or any
   other architecture-specific frontend.
2. **Static symbol isolation**: scan every shared module for prohibited
   architecture-specific identifiers/constants (NES/6502 address layouts,
   registers, PPU/APU/controller symbols, NROM constants; MIPS-specific opcode
   names like hard-coded `jal`/`jr`/`jsr`/`rts`/`rti`; fixed 16-bit NES
   addresses). Matches inside unrelated identifiers are excluded with word
   boundaries.
3. **Adapter isolation**: verify architecture-specific frontends import only
   from shared `openrecomp.*` modules and their own adapter
   (`adapters.nes6502`), not from sibling frontends or unrelated adapters.
4. **Non-NES path exercise**: run a synthetic/original MIPS32 fixture through
   the shared pipeline (P2-01 -> P2-02 -> P2-03 -> P2-04 -> P2-05 -> P2-06 ->
   P2-07) and verify deterministic host-source generation.
5. **Regression re-run**: run P2-01..P2-14, P2-20..P2-23, Phase-1 host gates,
   and source integrity.
6. **Determinism**: run the gate twice and compare stdout SHA-256.

## Findings and classification

| Check | Result | Classification |
| --- | --- | --- |
| Shared modules: prohibited architecture imports | 0 findings | Correctly isolated |
| Shared modules: prohibited architecture symbols | 0 findings | Correctly isolated |
| Architecture-specific adapters: non-generic dependencies | 0 findings | Correctly isolated |
| Generic data structures encode fixed addresses/register sets? | No | Architecture-neutral abstraction |
| Generic CFG supports variable instruction widths/direct/indirect flow? | Yes | Justified generic capability |
| Generic host emitter consumes neutral IR/program representations? | Yes | Architecture-neutral abstraction |
| Runtime services remain generic? | Yes | Architecture-neutral abstraction |
| NES-specific device behavior in shared layers? | None found | Correctly isolated to NES adapter |

All architecture-specific behavior discovered in the audit is confined to
`openrecomp/frontends/nes6502.py` and `openrecomp/frontends/nes_runtime.py`,
which depend only on the generic interfaces exported by the shared modules.
No corrections were required.

## Non-NES shared-path verification

A synthetic/original MIPS32 fixture (8 instructions, 32 bytes) was run through
the shared structural pipeline without using any NES-specific code:

| Layer | Outcome |
| --- | --- |
| P2-01 ProgramModel | `ProgramSource` architecture=`mips32-bounded-v1`, adapter=`adapters.mips32`, 8 `DecodedInstruction` objects |
| P2-02 CFG | Multiple blocks discovered; direct call continuation and `RETURN`-like unresolved edges preserved |
| P2-03 functions | Two functions: `fn_1000` (caller) and `fn_1090` (callee) |
| P2-04 call graph | One `INTERNAL_DIRECT` edge `fn_1000 -> fn_1090` |
| P2-05 translation units | Two units: `tu_fn_1000`, `tu_fn_1090` |
| P2-06 classification | Both `jr r31` sites classified `RETURN_LIKE` via explicit evidence |
| P2-07 host emitter | Deterministic portable C generated; source SHA-256 `be52ef25060e22f8c4677c2e87a2e89180f82ae88833c4d910ec11fe1881b9f6` |

The generated host source contains no NES/6502 terms and is byte-identical
across two independent emissions.

## Deterministic audit gate output

Two consecutive full gate runs produced byte-identical stdout:

```text
run1 sha256: 49a2a255e714d17ab00d224dc3f6f218df8eb0e00d26d60ecfc71c89404abb54
run2 sha256: 49a2a255e714d17ab00d224dc3f6f218df8eb0e00d26d60ecfc71c89404abb54
```

## Regression results

All required regressions passed:

```text
OPENRECOMP_PROGRAM_MODEL_V1=PASS tests=49
OPENRECOMP_CFG_V1=PASS tests=82
OPENRECOMP_FUNCTION_DISCOVERY_V1=PASS tests=67
OPENRECOMP_CALL_GRAPH_V1=PASS tests=61
OPENRECOMP_TRANSLATION_UNITS_V1=PASS tests=104
OPENRECOMP_INDIRECT_CONTROL_FLOW_V1=PASS tests=134
OPENRECOMP_HOST_EMITTER_V1=PASS tests=106
OPENRECOMP_GENERIC_RUNTIME_ABI_V1=PASS tests=169
OPENRECOMP_DETERMINISTIC_BUILD_V1=PASS tests=120
OPENRECOMP_MIPS32_END_TO_END_V1=PASS tests=108
OPENRECOMP_MIPS32_CALLS_MEMORY_V1=PASS tests=77
OPENRECOMP_MIPS32_DIRECT_CFG_V1=PASS tests=96
OPENRECOMP_RUNTIME_HOST_BOUNDARY_V1=PASS tests=80
OPENRECOMP_MIPS32_LARGER_FIXTURE_V1=PASS tests=82
OPENRECOMP_NES6502_PROGRAM_BRIDGE_V1=PASS tests=86
OPENRECOMP_NES6502_HOST_EMITTER_V1=PASS tests=74
OPENRECOMP_NES_RUNTIME_BRIDGE_V1=PASS tests=66
OPENRECOMP_NES_END_TO_END_V1=PASS tests=50
```

Phase-1 host gates:

```text
python tools/phase1_host_gates_v1.py
OPENRECOMP_PHASE1_HOST_GATES_PASS=2 FAIL=0 SKIPPED=0
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
```

Source integrity:

```text
python tools/phase1_host_gates_v1.py --only source-integrity
PASS                             source-integrity                 verified 129 manifest entries
```

## Source-integrity result

`PASS` — 128 manifest entries verified.

## Changed files

| File | Change |
| --- | --- |
| `tools/test_cross_architecture_neutrality_v1.py` | New P2-30 audit gate: static leakage checks, MIPS32 shared-path exercise, regression re-runs, evidence output. |
| `.openrecomp-phase2/evidence/P2-30/` | This evidence bundle. |
| `.openrecomp-phase2/{STATE,HANDOFF,STAGE_QUEUE}.md` | P2-30 PASS; advance `CURRENT_STAGE` to P2-40. |
| `SOURCE_SHA256SUMS.txt` | Updated to include the new gate (pre-existing `schemas/` glob gap remains deferred). |

No existing `openrecomp/*.py` implementation source was modified for this audit.
The shared architecture-neutral layers are reused unchanged.

## Commands and exit codes

```text
python tools/test_cross_architecture_neutrality_v1.py --evidence-dir .openrecomp-phase2/evidence/P2-30 --json .openrecomp-phase2/evidence/P2-30/p2_30_tests.json
OPENRECOMP_P2_30=PASS
OPENRECOMP_CROSS_ARCHITECTURE_NEUTRALITY_V1=PASS tests=14
exit 0
```

## Limitations and claim boundary

- This PASS proves that the current Phase-2 shared architecture remains
  appropriately architecture-neutral across the audited supported paths
  (MIPS32 and NES6502 through P2-01..P2-09).
- It does NOT prove that every future architecture can be integrated without
  new generic abstractions.
- It does NOT prove arbitrary NES, MIPS32, PS2, Xbox, or commercial-game
  compatibility.
- The audit is bounded to the shared modules listed above; platform adapters
  and future frontend modules are expected to remain isolated.

## Next stage

P2-40 — Generic runtime integration audit: prove backend neutrality and
document GB/GBC/SMS and future RT64-like extension points.
