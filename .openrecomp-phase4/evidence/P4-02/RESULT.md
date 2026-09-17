# P4-02 result (PASS)

Stage: `P4-02` Guest memory/runtime model (frozen queue row).
Gate: `tools/test_phase4_guest_memory_v1.py` (113 checks, sha256
`ac01573448d4a84dad0b519e6029db55022f2d4583b35767603f908aaa376725`).
Evidence: `.openrecomp-phase4/evidence/P4-02/`.

Markers issued:

- Stage marker: `OPENRECOMP_P4_02=PASS`
- Gate marker: `OPENRECOMP_PHASE4_GUEST_MEMORY_V1=PASS tests=113`
- Terminal marker (reserved): `OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN`
- General compatibility marker (never promoted):
  `OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN`

## Objective (frozen queue)

Implement and verify explicit guest memory regions and access semantics
including code/data/BSS/stack/heap where applicable, permissions, bounds,
alignment, endian handling and deterministic fault behaviour. Invalid/unmapped
accesses fail closed.

## Implementation (additive Phase-4 files only)

- `.openrecomp-phase4/src/p4_guest_memory_v1.py` — the explicit guest memory
  model: region kinds (`code`, `rodata`, `data`, `bss`, `stack`, `heap`) with
  declared read/write/execute permissions, validated non-overlap/bounds/no-wrap
  and a W^X rule; byte-addressed widths 8/16/32/64 with explicit
  little/big endianness and an alignment policy (`allow`, `require-natural`);
  deterministic fail-closed faults (`UNMAPPED`, `PERMISSION`, `ALIGNMENT`,
  `WIDTH`, `ENDIANNESS`, `OVERFLOW`) with a total mapping to the P2-08/P4-01
  ABI failure codes; canonical state document and sha256 fingerprint; an
  `AbiMemoryService` adapter and the pinned frozen Phase-3 instance adapter
  (`g_image` window parse, emitted region table parse).
- `tools/test_phase4_guest_memory_v1.py` — the P4-02 gate.
- `.openrecomp-phase4/SOURCE_SHA256SUMS.txt` — grown additively to eight
  entries.

No frozen Phase-1/Phase-2/Phase-3 file, gate, evidence byte or tag was
modified.

## Verification highlights

- `region:*` / `reject:*`: kind default permissions, W^X rejection, duplicate
  names, overlaps, zero size, address wrap, oversized or disallowed file data
  (BSS/stack/heap), invalid endianness/alignment policies.
- `access:*`: widths 8/16/32/64, little/big byte order, masking, unaligned
  byte-addressed access, code fetch, writes to data/BSS/stack/heap, byte
  round-trips, BSS zero initialisation.
- `fault:*` / `align:*`: unmapped, gap, permission (read/write/fetch),
  cross-region end, width, endianness, negative/bool address, address
  overflow, and deterministic natural-alignment faults under the strict
  policy.
- `abi:*`: total fault mapping against the P4-01 contract and P2-08 codes;
  `AbiMemoryService` statuses (0/1/2) match the frozen support semantics;
  differential agreement with `rt.RuntimeMemory` on allowed flat accesses.
- `instance:*`: the frozen `coremark_program.c` (`5199e2f0...`) parses; the
  `g_image` window is `3eecfc95...` (65536 bytes, ELF magic); the emitted
  four-region table is reproduced exactly; the permissioned model regions
  merge to exactly the emitted coverage; the entry word, text/rodata/data
  reads, BSS zero-fill (including the tail and the guest stack window inside
  BSS), and fail-closed writes to headers/text/rodata all behave as declared;
  ABI width-64 rejection and text-write rejection match the frozen profile.
- `state:*`: deterministic snapshots/fingerprints/documents, fingerprint
  sensitivity, no host paths.

## Determinism

- Two consecutive official gate runs: exit 0, empty stderr, stdout
  byte-identical raw (3855 bytes, `5cfc58f1...`) and LF (`4545d2b4...`), and
  `p4_02_tests.json` byte-identical across both runs (`77f49e22...`).
- Evidence: `official_runs.json`, `determinism.json`.

## Regressions

- `tools/test_runtime_abi_v1.py` (P2-08) `PASS tests=169`.
- `tools/test_phase4_runtime_abi_v1.py` (P4-01) `PASS tests=156`,
  stdout byte-identical (`81c96314...`).
- `tools/phase1_host_gates_v1.py` `PASS=44 FAIL=0 SKIPPED=2`.
- `tools/public_safety_scan.py` `OPENRECOMP_PUBLIC_SAFETY=PASS`.
- `tools/test_phase4_boundary_v1.py` (P4-00) `PASS tests=74`, stdout
  byte-identical (`953312d0...`), re-run with the documented frozen-gate
  boundary-context hygiene (`regression_hygiene.json`).

## Limitations

- The model is declared and verified, not yet wired as the execution backing
  store of the runtime: the frozen Phase-3 native path still uses the flat
  P2-08 `RuntimeMemory`; adopting the region model in an execution path is
  later-stage scope (P4-08/P4-09).
- Permission faults map to `MEMORY_OUT_OF_RANGE` at the generated-code
  boundary (matching the frozen support's behaviour); the precise fault kind
  (`PERMISSION`, `ALIGNMENT`, ...) is preserved in the model's fault record
  and evidence, and no new ABI failure code is invented.
- Region kinds other than the five declared are unsupported and rejected.
- `GENERIC_RUNTIME_STATUS=NOT_PROVEN`; the terminal and general compatibility
  markers stay reserved.

## Next stage

P4-03 — Runtime service mediation.
