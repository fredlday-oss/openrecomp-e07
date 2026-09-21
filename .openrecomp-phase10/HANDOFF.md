# OpenRecomp Phase 10 Handoff

## Current boundary

- work branch `phase10/ps1-commercial-game-native-v1`, based exactly on the
  Phase-9 terminal commit `08c639d9032a364163f2985432744be420d402eb`
  (tree `900dccf06ce3d5df7b499a9f05a6ceea060114d7`);
- `P10-00` `PASS` (192 checks): frozen Phase-9 boundary, fixture/disc identity,
  inherited frontier reproduction, toolchains, control plane and frozen queue;
- `P10-01` `PASS` (111 checks): BREAK/SYSCALL classification, public synthetic
  reproducers and the exact private site context;
- `P10-02` `PASS` (65 checks): `CONTROL_WITHOUT_DELAY_SLOT` reconciled by the
  additive exception-aware structure bridge; the Hercules structure completes;
- evidence in `.openrecomp-phase10/evidence/P10-00/`, `P10-01/` and `P10-02/`.

## Immediate next action

`P10-03` - Hercules CPU/control frontier iteration from the new frontier.

The next genuine reachable requirements are, in address order:

1. `sh` at `0x80011a60` - the lowest-address reachable op without a
   host-emitter semantic rule (supported decode, missing rule);
2. the rest of the 24 unruled op types / 286 reachable instructions recorded in
   `.openrecomp-phase10/evidence/P10-02/structure_reconciliation.json`:
   `addi`, `and`, `bgez`, `bgtz`, `blez`, `bltz`, `break`, `jalr`, `lh`,
   `lhu`, `lwl`, `lwr`, `mfhi`, `mult`, `sh`, `slt`, `slti`, `sltiu`, `sltu`,
   `subu`, `swl`, `swr`, `syscall`, `xori`;
3. the 18 `jr` indirect jumps and 22 `jalr` indirect calls (40 unresolved
   indirect control sites) - these need an explicit, fail-closed indirect
   dispatch decision: either evidence-backed resolution or a runtime-mediated
   dispatch that fails closed on an unknown target. No target may be guessed.

For new CPU semantics: create independent vectors, use the
architecture-neutral implementation where possible, add fail-closed negatives,
and implement only reachable requirements. `addi` overflow must fail closed
explicitly rather than wrapping silently; `lwl`/`lwr`/`swl`/`swr` merge
semantics must be exact; `mult`/`mfhi` need explicit HI/LO state.

## Known work queued after P10-03

- `P10-04` .. `P10-11`: BIOS frontier, native execution entry, dynamic I/O
  discovery, GPU, interrupt/DMA/timing, CUE/BIN CD-ROM/filesystem/streaming,
  SPU/controller/game-loop, highest milestone;
- `P10-12`, `P10-90`, `P10-91`, `P10-99`: hardening, whole-project regression,
  evidence closure and the final bounded verdict.

## Private fixture notes

- primary executable `SLUS_005.29` (PS-X EXE), entry `0x800132e8`, text
  `0x80010000` size `0x0001f000`, stack `0x801ffff0`;
- single-track MODE2/2352 CUE; the CUE is the logical disc entry point;
- the boot extent on the disc is byte-identical to the primary executable;
- never record payload bytes, disassembly excerpts, disc sectors or
  reconstructive derived data.

## Working-tree residue (preserve untouched)

Tracked Phase-3 evidence files under `.openrecomp-phase3/evidence/P3-00/` are
modified by a historical verification-context re-run, and untracked residue
exists under `.openrecomp-phase2/`, `.openrecomp-phase3/`, `artifacts/` and
`tools/test_build_package_reproducibility_v1.py`. This residue predates Phase
10 and must never be committed, deleted or altered by Phase-10 work.
