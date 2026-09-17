# P3-09 result (PASS)

Stage: `P3-09` independent MIPS32 reference + equivalence (frozen queue row).
Gate: `tools/test_phase3_reference_equivalence_v1.py` (39 checks).
Evidence: `.openrecomp-phase3/evidence/P3-09/`.

Markers issued:

- Stage marker: `OPENRECOMP_P3_09=PASS`
- Gate marker: `OPENRECOMP_PHASE3_REFERENCE_EQUIVALENCE_V1=PASS tests=39`
- Terminal marker (reserved): `OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=NOT_PROVEN`

## Scope

P3-09 executes the audited CoreMark ELF with an independently written MIPS32
reference and proves deterministic observable equivalence with the P3-08 native
runtime. New Phase-3 files only:

- `.openrecomp-phase3/src/p3_reference_mips32_v1.py` — independent little-endian
  ELF32 loader (PT_LOAD segments, flat 64 KiB image, region permissions),
  independent raw-word decoder for the audited op set, exact MIPS32 semantics
  with delay slots, HI/LO, region-checked memory access and the two MMIO
  windows, plus the documented FNV-1a 64 observable digest;
- `tools/test_phase3_reference_equivalence_v1.py` — the P3-09 gate;
- `.openrecomp-phase3/SOURCE_SHA256SUMS.txt` — grown additively from seventeen
  to nineteen entries; the earlier gates now expect nineteen entries and still
  emit byte-identical stdout.

## Independent loader cross-check

- image sha256
  `3eecfc957c4ed147544d2aa98c6e4f4d7aac41957e531cdfe01c2555ff0a91ae` equals
  the P3-07 host image exactly;
- regions `0x0+0x134 r--`, `0x1000+0x367C r-x`, `0x4680+0x778 r--`,
  `0x4E00+0x4820 rw-` equal the P3-02 segment table;
- the independent decoder classifies 3479 words with the exact frozen op
  histogram (e.g. `addiu` 654, `or` 345, `lw` 275, `sw` 205, `jr` 52,
  `movz` 35, `divu` 4, `teq` 4, `jalr` 1).

## Full-run equivalence

The reference executed the complete program (394,997,250 steps) and matches the
P3-08 native observable in every compared field:

| field | value (native == reference) |
| --- | --- |
| `exit_status` | `0` |
| `steps` | `394997250` |
| `pc` | `0x00004564` |
| `hi` / `lo` | `0x0000000d` / `0x00000000` |
| `uart_bytes` | `499` |
| `uart_hex` | CoreMark output (see `reference_observable.json`) |
| `state_fnv1a64` | `0x78651c29dd149ab1` |
| `failed` / `failure` | `0` / empty |

The reference's final image sha256 is `67a14938...` and the final register
dump sha256 is `21cd49e7...`. The UART stream contains CoreMark Size 666,
Iterations 1000, the published validation CRCs (`seedcrc 0xe9f5`,
`crclist 0xe714`, `crcmatrix 0x1fd7`, `crcstate 0x8e3a`, `crcfinal 0xd340`) and
`Correct operation validated.`

## Reference fail-closed negatives

Synthetic minimal ELFs proved the reference's fail-closed paths: divide by
zero, taken `teq` (code preserved), unaligned indirect jump target,
out-of-image memory access and PC outside the image, plus rejection of
malformed ELF headers. Each produced the exact expected deterministic message.

## Image-fidelity correction (documented)

This stage's independent loader exposed a genuine cross-stage contradiction:
the P3-07 emitter had built `g_image` from the allocated sections instead of
the PT_LOAD region bytes, so the 308-byte read-only ELF header region
(`0x0..0x134`, never read by the audited guest) was zero in the host program.
Repaired at the source within P3-09: the emitter now embeds the exact P3-02
load image, the P3-07 gate gained an explicit
`emission:image-equals-load-image` check (68 checks), and the P3-07/P3-08 gates
were re-run on the corrected sources and re-passed with regenerated evidence.
No execution observable changed; the state digest now matches the reference
exactly. This is recorded as a stage-internal repair in `STATE.md`,
`HANDOFF.md` and the `STAGE_QUEUE.md` reconciliation log; no stage ID, order,
name or outcome scope changed.

## Verification

- 39 gate checks: source integrity (root manifest 134 entries frozen, Phase-3
  manifest 19 entries), loader/image/region/decoder cross-checks, full-run
  reference execution, ten-field equivalence, five runtime negatives plus
  malformed-ELF rejection and artifact hashing.
- Determinism (and the official two-run proof): two independent gate process
  invocations emitted byte-identical stdout (raw sha256
  `722a4cd87bc6eb0fa6ef513aadfe3b7e1198156fd54314b8df1838c158a0a4d2`, 1742
  bytes, empty stderr, exit 0); all evidence artifacts are deterministic
  (no wall-clock or host values).
- Regressions all exit 0 with empty stderr and byte-identical stdout: P2-99
  `PASS tests=202` (`66913e57...`), P3-00 `PASS tests=61` (`a039bbff...`),
  P3-01 `PASS tests=76` (`81eede03...`), P3-02 `PASS tests=197`
  (`f24f4cef...`), P3-03 `PASS tests=201` (`15e20a2c...`), P3-04
  `PASS tests=126` (`412544a4...`), P3-05 `PASS tests=202` (`12bf87d7...`),
  P3-06 `PASS tests=123` (`23d2f1c2...`), P3-07 `PASS tests=68`
  (`26b871bf...`), P3-08 `PASS tests=55` (`cdc7abbf...`), Phase-1 host gates
  `PASS=44 FAIL=0 SKIPPED=2` (`2a9d1bba...`), public safety `PASS`
  (`ad022ff1...`).

## Claim boundary

P3-09 proves deterministic observable equivalence for this one audited
CoreMark MIPS32 program only, between the P3-08 native execution and an
independently written reference. It claims no arbitrary MIPS32, PS1 or PS2
compatibility. The terminal Phase-3 marker remains reserved and `NOT_PROVEN`
until the remaining frozen stages (package + whole regression, evidence index,
final verdict) pass.
`COREMARK_STATUS=NOT_PROVEN`.
