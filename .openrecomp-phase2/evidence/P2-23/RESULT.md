# P2-23 NES synthetic end-to-end equivalence — result

Stage: `OPENRECOMP_NES_END_TO_END_V1`.

Verdict: **PASS**.

## Markers

```text
OPENRECOMP_NES_END_TO_END_V1=PASS tests=50
```

## What was proven

The complete Phase-2 NES path was exercised end-to-end on a
synthetic/original NES/NROM fixture, and the native executable's
observable output is byte-identical to an independent reference
interpreter that uses the same NES runtime adapter.

* New dedicated gate `tools/test_nes_end_to_end_v1.py`.
* Synthetic/original 59-instruction NES6502 fixture (144 bytes,
  SHA-256 `dfadcbe759121b0705f2a7db3295127b7adceb403a6254897caee85f8a1c44c2`).
* The P2-21 26-byte core region and the P2-22 controller-probe bytes are preserved;
  the previously placeholder frame/audio triggers are replaced by real host-call thunks.
* Pipeline traversal: adapter decode -> P2-01 ProgramModel -> P2-02 CFG -> P2-03
  function discovery -> P2-04 call graph -> P2-05 translation units -> P2-06
  indirect-control-flow classification (`EXTERNAL_OR_RUNTIME_MEDIATED` runtime-service sites)
  -> P2-07 host emitter -> P2-08 generic runtime ABI -> P2-09 deterministic build.
* Generated source fingerprint: `9819b40e9909b4056211f6f452297b502b99bc4be4f96fe797cdcdfd6aaf2b78`.
* Native executable returncode 0; expected vs actual stdout identical.

## Determinism

* Three native executions produced byte-identical stdout: `c53c8ae8606b236c80d7c3fcd10d24da4f00752e15d933dcbdeb2f2882e81f82`.
* Two independent full gate runs produced byte-identical stdout: `96dbf5965310bc17a21bfc9fdd38042d30067b1efe7eae41522033dcc2ad1540`.

## Source integrity

`python tools/phase1_host_gates_v1.py --only source-integrity` reported:

```text
PASS                             source-integrity                 verified 128 manifest entries
PASS                             wasm-runner-intact               sha256=b973c3c52712937d59a15f2e50c405830be9882b5c457c05b1248b12405613ca
OPENRECOMP_PHASE1_HOST_GATES_PASS=2 FAIL=0 SKIPPED=0
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
```

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
OPENRECOMP_NES6502_HOST_EMITTER_V1=PASS tests=74
OPENRECOMP_NES_RUNTIME_BRIDGE_V1=PASS tests=63
OPENRECOMP_NES_PLATFORM_V1=PASS tests=10
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
```

## Evidence artifacts

`.openrecomp-phase2/evidence/P2-23/` contains:

* `RESULT.md` (this file)
* `RESULT.json`
* `changed_files.txt`
* `fixture.txt`
* `pipeline_*.txt`
* `generated_source.c` + `generated_source_sha256.txt`
* `build_manifest.json` + `build_run_*.txt`
* `native_execution.txt`
* `expected_vs_actual.txt`
* `reference_comparison.txt`
* `determinism.txt`
* `gate_determinism.txt` + `p2_23_run1.txt` + `p2_23_run2.txt`
* `source_integrity.txt`
* regression captures for prior gates

## Limitations and non-claims

* Proves only the bounded synthetic NES/NROM fixture described above.
* No full PPU/APU emulation, no commercial-ROM compatibility and no whole-guest
  equivalence is claimed.
* Mapper 0 (NROM) only; unsupported mappers, disabled I/O, expansion areas and
  PPU/APU register access fail closed.
* The final `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS` marker remains
  reserved for P2-99.
