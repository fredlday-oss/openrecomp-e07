# P2-22 NES runtime bridge — result

Stage: `OPENRECOMP_P2_22_NES_RUNTIME_BRIDGE_V1`.

Verdict: **PASS**.

## Markers

```text
OPENRECOMP_P2_22=PASS
OPENRECOMP_NES_RUNTIME_BRIDGE_V1=PASS tests=66
```

## What was proven

The generic runtime ABI from P2-08 has been connected to a bounded NES platform
adapter without adding NES assumptions to the shared architecture-neutral layers.

* New module `openrecomp/frontends/nes_runtime.py`: `NESRuntimeAdapter` routes
  NES CPU-visible memory through `RuntimeMemory`, maps `RuntimeInputSnapshot` to
  the documented NES standard-controller protocol, and exposes frame/audio
  submission through declared host-call services (`nes.frame.submit`,
  `nes.audio.submit`).
* The adapter uses only the generic runtime contracts (`RuntimeState`,
  `RuntimeMemory`, `RuntimeInputSnapshot`, `RuntimeFrame`, `RuntimeAudio`,
  `RuntimeServiceTable`). It does not add NES-specific symbols to
  `openrecomp/runtime_abi.py`, `openrecomp/host_emitter.py`,
  `openrecomp/build_pipeline.py` or any other shared layer.
* The synthetic fixture preserves the 26-byte P2-21 6502 region unchanged and
  expands it with controller-probe / frame/audio-trigger bytes so the runtime
  contracts are exercised (SHA-256
  `cc57bba3124f264cb6f4ec2b0e83cb82d3a9eeea551d18c098278c7eef827763`).
* Memory contract exercised: 2 KiB internal RAM mirrors, PRG-ROM read and
  16 KiB NROM mirror, PRG-RAM fail-closed when absent, disabled I/O and
  expansion-area fail-closed.
* Input contract exercised: generic digital channels are mapped to NES
  controller bits (A/B/Select/Start/Up/Down/Left/Right); the guest-visible
  `$4016`/`$4017` serial protocol returns the mapped state with documented
  open-bus bits.
* Frame contract exercised: `nes.frame.submit` reads a pixel payload from guest
  memory and submits a deterministic `RuntimeFrame` through the generic frame
  contract.
* Audio contract exercised: `nes.audio.submit` reads a PCM payload from guest
  memory and submits a deterministic `RuntimeAudio` through the generic audio
  contract.
* Host-call ABI integration exercised: service ids, numeric ids, macros and
  generic `RuntimeState.host_call` dispatch all work; arity mismatch fails
  closed with `HOST_CALL_ARITY`.

## Determinism

* Two consecutive P2-22 gate runs produced byte-identical stdout:
  `4ae725be384b991c58d5e072930603b93c72c939df89c18f07749ae5c3db7b5c`.
* The recorded runtime-state fingerprint after the contract scenario is:
  `55da1916e5f56b3e663beb37ceb6486fba76957cb66027b64db1223f21639759`.

## Source integrity

`python tools/phase1_host_gates_v1.py --only source-integrity` reported:

```text
PASS source-integrity verified 127 manifest entries
```

Changed/new files (SHA-256):

```text
b4337eeb6933475f77cd414d4bac229c2614bf0c84aa03f7a2d9b968d6478f4d  openrecomp/frontends/nes_runtime.py
e0765124b4f483d782afafd9bad12acf9bca6622a97ac4e77e4568a79563c361  tools/test_nes_runtime_bridge_v1.py
0edb599ec743e5ecc1cfde5ee057fe83867bb06c7d81f3344869a5b3bc031ad8  SOURCE_SHA256SUMS.txt
```

## Regressions

All relevant prior and Phase-1 gates were re-run and passed:

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
OPENRECOMP_NES_PLATFORM_V1=PASS tests=10
OPENRECOMP_PHASE1_HOST_GATES_PASS=2 FAIL=0 SKIPPED=0
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
PASS source-integrity verified 127 manifest entries
```

(The full `phase1_host_gates_v1.py` inventory includes toolchain-gated gates
that are skipped on this host; the relevant runnable subset was verified.)

## Evidence artifacts

`.openrecomp-phase2/evidence/P2-22/` contains:

* `RESULT.md` (this file)
* `RESULT.json`
* `changed_files.txt`
* `fixture.txt`
* `adapter.txt`
* `frame_submission.txt`
* `audio_submission.txt`
* `input_mapping.txt`
* `gate_determinism.txt`
* `p2_22_run1.txt`, `p2_22_run2.txt`
* `p2_22_tests.json`
* `source_integrity.txt`
* regression captures for P2-01..P2-14, P2-20, P2-21, NES platform and source
  integrity

## Limitations and non-claims

* Proves only the runtime-bridge infrastructure for a bounded synthetic NROM
  fixture. No full PPU/APU emulation, no commercial-game compatibility and no
  whole-guest equivalence is claimed.
* PPU register reads/writes, expansion areas, disabled I/O and unsupported
  mappers fail closed.
* Frame/audio submission is a bounded adapter surface; the runtime does not
  implement a renderer or audio backend.
* The final `OPENRECOMP_PHASE2_END_TO_END_RECOMP_PROOF=PASS` marker remains
  reserved for P2-99.

## Next stage

P2-23 — NES end-to-end proof: `synthetic/open NROM fixture → host executable →
deterministic observable equivalence`.
