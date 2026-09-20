# OpenRecomp Phase 9 Handoff

STATUS: Phase 9 `IN_PROGRESS` -- `P9-00` boundary and acceleration control
plane established and `P9-01` PS-X EXE ingestion complete at the frozen
Phase-8 terminal boundary. The terminal marker
`OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF` remains `NOT_PROVEN`;
`OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` and
`OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN` are permanent.

## Baseline

- Branch: `phase8/mips32-end-to-end-native-v1`.
- Phase-8 terminal commit:
  `61136fc37cf0810e64241addd8f57a91872bc0af`.
- Phase-8 terminal tree:
  `f9262497b82fe0027c3b23432ba7bd8cbccdf433`.
- Phase-8 terminal verdict (P8-99): `PASS` for the exact bounded audited
  public Phase-8 fixture and behaviour only.
- Phase-8 terminal tag: absent (`ABSENT_RECONCILED`); no tag is fabricated.

## Objective

Prove one bounded PS1 platform/runtime integration path by reusing the
existing Phase-8 MIPS32 end-to-end native pipeline:

```
PS-X EXE
  -> PS-X EXE ingestion / load-image reconstruction
  -> existing MIPS32 decode
  -> shared ProgramModel / CFG / functions / call graph / translation units
  -> existing host emitter
  -> PS1 platform runtime adapter
  -> deterministic native build / execution
  -> bounded validation
```

The private Hercules `SLUS_005.29` fixture is a legally obtained local
validation input only. It is never a public `PASS` criterion on its own and
contributes only non-reconstructive metadata to evidence. Any public terminal
claim requires a legally redistributable OpenRecomp-authored or openly
licensed PS1 fixture.

## P9-00 outcome

- the exact Phase-8 terminal commit/tree/branch boundary and P8-99 terminal
  evidence were verified; no Phase-8 terminal tag exists and none was created;
- the frozen Phase-1 through Phase-8 tracked files and Phase-8 terminal
  evidence hashes re-verified on disk; the Phase-8 source manifest re-verifies
  unchanged; the inherited Phase-6/Phase-7 reconciliation records are present;
- the additive Phase-9 control plane, fixture policy, evidence schema,
  acceleration policy (fast/terminal gates, the
  `openrecomp-phase9-analysis-cache-v1` cache key contract, incremental-build
  policy, private-fixture cache handling), frozen queue and source manifest
  were established;
- the recorded toolchain set (Python, Git, clang/clang-cl, lld-link, Ninja,
  CMake, Zig 0.13.0) was captured in `evidence/P9-00/toolchains.json`;
- the P9-00 gate passed twice with byte-identical stdout, empty stderr and
  exit 0. Evidence is under `.openrecomp-phase9/evidence/P9-00/`.

## Frozen queue

Rows `P9-01` .. `P9-99` are frozen at the P9-00 `PASS` boundary in
`.openrecomp-phase9/STAGE_QUEUE.md`. The next stage is `P9-02` (PS1 executable
image and memory-map contract).

## P9-01 outcome

- additive, fail-closed PS-X EXE ingestion
  (`.openrecomp-phase9/src/p9_psx_exe_v1.py`) and an original deterministic
  PS-X EXE builder (`.openrecomp-phase9/fixture/psx_fixture_builder_v1.py`)
  were established;
- 163 checks: canonical synthetic round-trip, BSS/GP positive paths, identity
  leak checks and 22 malformed/unsupported forms rejected with stable codes;
- the private Hercules fixture was ingested and reduced to
  non-reconstructive metadata (file/payload hashes, header fields,
  reserved-region hash and counts) with no executable bytes committed;
- the P9-01 gate passed twice with byte-identical stdout, empty stderr and
  exit 0. Evidence is under `.openrecomp-phase9/evidence/P9-01/`.

## Known work for P9-02

- define the explicit PS1 guest address-space model (2 MiB main RAM KSEG0
  window, KSEG1 mirror classification, scratchpad/IO/BIOS ranges as explicit
  unsupported-or-service regions), region permissions and stack contract;
- map the ingested payload into a bounded flat image without silent masking;
- no invented mappings: every address translation decision is explicit and
  fail-closed.
