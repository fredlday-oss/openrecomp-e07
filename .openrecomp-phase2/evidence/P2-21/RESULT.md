# P2-21 NES6502 host emitter path — result

Stage: `OPENRECOMP_P2_21_NES6502_HOST_EMITTER_V1`.

Verdict: **PASS**.

## Markers

```text
OPENRECOMP_P2_21=PASS
OPENRECOMP_NES6502_HOST_EMITTER_V1=PASS tests=74
```

## What was proven

The architecture-neutral Phase-2 host-emitter/runtime path lowers the NES6502
ProgramModel and translation-unit output from P2-20 into an executable host
program without NES-specific changes to the shared layers.

* The fixture is the same 26-byte synthetic NES6502 region used in P2-20
  (SHA-256 `0a236023c59fd5363d0ebdd6ffb18d9b4e792ebeaa11a72ca513b183539fa398`).
* Real pipeline traversal: P2-01 ProgramModel -> P2-02 CFG (8 blocks) -> P2-03
  function discovery (`fn_8000`, `fn_8018`) -> P2-04 call graph (one
  `INTERNAL_DIRECT` edge) -> P2-05 two translation units -> P2-06 one
  `UNRESOLVED_INDIRECT_JUMP` site at `0x8012` -> P2-07 host emitter -> P2-08
  generic runtime ABI (checked byte memory boundary) -> P2-09 deterministic
  build.
* Emitted source: `generated_source.c`, SHA-256
  `7d42947f658f0e7dcb146f3c5f2dd19c742c94bb8cf3e6b2ae8feb789758fd74`.
* Register file exposed to the emitter: `a`, `c`, `ea`, `n`, `tmp`, `x`, `z`
  (6502 A/X registers, C/Z/N flag temporaries, effective-address temp).
* The generated native executable fails closed at the unresolved indirect
  `jmp ($0300)` as required, with the same A/X state as the reference
  interpreter.

## Representative behavior exercised

* Register load: `ldx #$03`
* Arithmetic/logical: `adc #$05`, `clc`
* Conditional branch: `bne`
* Counted loop: three iterations of the `0x8002` block
* Indexed memory access: `sta $0400,x`
* Direct subroutine call/return: `jsr helper` / `inx` / `rts`
* Direct jump: `jmp dispatch`
* Unresolved indirect jump: `jmp ($0300)` remains fail-closed (no target is
  invented)

## Observable comparison

Independent Phase-1 reference interpreter (`tools/nes6502_reference_v1.py`):

* trace length: 21 executed instructions
* final halted PC: `0x0202`
* final `a = 15`, `x = 1`

Native generated executable:

* `failed=1`, `error=unresolved indirect jump`
* `reg[a]=15`, `reg[x]=1`

The A and X registers match the reference exactly. The full RAM checksums
differ because the reference models the 6502 stack push/pop performed by
`jsr`/`rts` (modifying bytes at `0x01FE/0x01FF`), while the structural
call/return path emits native C function calls and does not model the 6502
stack. The explicitly modeled stores (`sta $0400,x` at `0x0401-0x0403`) match.

## Determinism

* Two consecutive P2-21 gate runs produced byte-identical stdout:
  `e66406e043b9dab859f5cf56ea537f333be7b59619e8c7bbb06bad4fd45f57e4`.
* Two consecutive native executable runs produced byte-identical stdout:
  `99848de179b0b120e42eed2e4b68e6e14a2dfa950d1065ac615dd8a845d27f3c`.
* Two independent `/Brepro` clang-cl/lld-link builds produced byte-identical
  generated source, objects and executable; classification
  `EXECUTABLE_REPRODUCIBLE`.

## Build provenance

Toolchain detected by the P2-09 pipeline:

* `clang-cl.exe` + `lld-link.exe`
* `/Brepro` passed to compiler and linker
* No binary post-processing

Executable SHA-256: `dbba1e3a86274d2944a38de575faee48d04e7748e8a150c93a5adbb0325e35f8`.

## Regressions

All relevant prior gates were re-run and passed:

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
OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
PASS source-integrity verified 125 manifest entries
```

The two skipped Phase-1 gates (`e07-hardened-end-to-end`, `external-repro-v1`)
require POSIX/bash/clang/gcc/node and are correctly skipped on this host.

## Source integrity

`python tools/phase1_host_gates_v1.py --only source-integrity` reported:

```text
PASS source-integrity verified 125 manifest entries
```

## Evidence artifacts

`.openrecomp-phase2/evidence/P2-21/` contains:

* `RESULT.md` (this file)
* `RESULT.json`
* `fixture.txt`
* `bridge_summary.txt` (structural summary)
* `pipeline_cfg.txt`
* `pipeline_functions.txt`
* `pipeline_call_graph.txt`
* `pipeline_translation_units.txt`
* `pipeline_indirect_control_flow.txt`
* `generated_source.c`
* `generated_source_sha256.txt`
* `build_manifest.json`
* `build_run_1.txt`, `build_run_2.txt`
* `native_execution.txt`
* `expected_vs_actual.txt`
* `reference_comparison.txt`
* `determinism.txt` (native executable stdout determinism)
* `gate_determinism.txt` (P2-21 gate stdout determinism)
* `p2_21_gate.txt`
* `p2_21_tests.json`
* `host_gates.json`
* regression captures for P2-01..P2-14, P2-20 and source integrity

## Limitations and non-claims

* Proves only this bounded synthetic 15-instruction NES6502 fixture.
* The 6502 stack effects of `jsr`/`rts` are not modeled; call/return is handled
  by the structural path as native C function calls.
* Memory accesses are byte-wide but emitted through the generic runtime ABI
  using the configured 16-bit word width; the fixture runtime support
  interprets the ABI call as a byte access. This is a documented fixture
  simplification, not a claim about general NES memory mapping.
* Flags other than Z/N and carry for `adc`/`clc` are not in the emitted subset;
  the semantic rules only cover the operations exercised by the fixture.
* No commercial ROM, iNES parser, mapper support, PPU/APU/controller runtime,
  or whole-guest equivalence is claimed.
* The final `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS` marker remains
  reserved for P2-99.

## Next stage

P2-22 is queued for the first real NES ROM integration/validation stage using a
legally obtained ROM supplied externally by the user. The ROM must remain
outside Git; repository evidence may contain hashes, metadata, addresses,
counts, classifications and derived results, but no copyrighted ROM bytes.
