# P6-12 Reusable ROM-to-Native Workflow - Result

Verdict: `PASS` (bounded audited public MMC1 workflow, end to end)

## Baseline

- Branch `phase6/nes-compat-v1` at the P6-11 boundary commit
  `150282b479d5e737e0251bf76e9f3126914de792`, tree
  `445840ff30e5ea1034606fb17edffebcf4d9cece` (Phase-5 frozen boundary
  `e8d3627a622d0ca3196b117c5112f29fabdb49e7`; tag object
  `b5d6832ba2374b810f4c24500ed9093a9481fd8d`, tree
  `468fb9788350de393d3de2ca9471b7d874ee8dc9`).

## Objective (frozen queue)

Provide one deterministic command/workflow that accepts a local ROM path,
performs inventory and compatibility classification, statically recompiles
supported binaries, generates native source/build artifacts, builds the native
target and reports exact fail-closed blockers. Never package the source ROM.
Unsupported mapper/hardware paths terminate with explicit reasons.

## Changes (additive)

- `.openrecomp-phase6/src/p6_workflow_v1.py`: new reusable deterministic
  ROM-to-native workflow (module + CLI). It inventories the image by
  metadata/hash only, classifies mapper/platform support against
  `MMC1_SUBSET_V1` and the variant ledger, recovers the documented reachable
  frontier, classifies undocumented opcodes and unresolved indirect targets,
  statically recompiles only a contiguous fully documented fixed-bank region
  with no runtime-bank ambiguity and no undeclared indirect site, generates the
  host program and MMC1 runtime support sources into a caller-owned workspace,
  builds through the shared Phase-2 pipeline and executes the generated native
  binary through the typed runtime ABI (original 6502 guest code is never
  executed on the host). No ROM file is copied, packaged or written by the
  workflow.
- `tools/test_phase6_workflow_v1.py`: new P6-12 gate exercising the workflow on
  the public MMC1 proof fixture end to end plus fail-closed classifications,
  anchors to the frozen P6-07/P6-08 identities, CLI determinism, workspace
  ROM-copy hygiene and earlier Phase-6 regressions.
- `.openrecomp-phase6/SOURCE_SHA256SUMS.txt`: adds the two new source
  identities.
- `.openrecomp-phase6/STATE.md`, `STAGE_QUEUE.md`, `HANDOFF.md`: stage
  bookkeeping.
- No frozen Phase-5/6 module, gate, evidence or control-plane file was
  modified; the workflow composes the audited P6-01..P6-09 modules read-only.

## Official gate

- Runner: `python .openrecomp-phase6/src/p6_stage_runner_v1.py --stage P6-12
  --script tools/test_phase6_workflow_v1.py --evidence-dir
  .openrecomp-phase6/evidence/P6-12 --tests-json p6_12_tests.json`
- Two consecutive runs: exit 0, empty stderr, stdout byte-identical:
  - stdout: 4375 bytes raw, raw sha256
    `d62911363f127844fe5dd4fc2854c8064d458ac1a4c3aeec47f4fcbb7398cd76`,
    LF sha256
    `275fa9993fd0c30c29cd888171ed5f42cac4bab2995c071bc5b06327829efe19`.
  - `p6_12_tests.json` sha256
    `85664a79fa5e3f4f1f85efee506c846ccac396db2d0773253035b54a0062d6f3`,
    `tests=111`; both runs produced the same tests-json hash.
- Markers: `OPENRECOMP_P6_12=PASS`,
  `OPENRECOMP_PHASE6_ROM_TO_NATIVE_WORKFLOW_V1=PASS tests=111`,
  `OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN`,
  `OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`.

## Workflow result on the public MMC1 proof fixture (full success path)

- Input: `LOCAL_USER_SUPPLIED_ROM`, sha256 `9e10dce5...`, 98320 bytes; the
  source ROM was not copied (`source_rom_copied=false`) and no byte-identical
  ROM copy exists anywhere in the workspace.
- Inventory: `ines`, mapper 1/submapper 0, horizontal, 64 KiB PRG / 32 KiB
  CHR, no PRG-RAM/battery/trainer; vectors NMI `$C1F8` / RESET `$C000` /
  IRQ `$C235`.
- Mapper/platform: `SUPPORTED_MMC1`, variant profile
  `discrete_mmc1_chr_rom_no_wram`; power-on registers `0C 00 00 00`, PRG
  windows `(0, 3)`, CHR mode 0, one-screen lower, PRG-RAM disabled.
- Frontier: documented walk `OK`; code region `$C000-$C23B`, contiguous, 262
  reachable instructions / 571 bytes, zero low-window reachable instructions.
- Opcode frontier: `SUPPORTED`, 35 documented opcode forms, no unsupported
  entries. Indirect control flow: `RESOLVED`, the single declared
  `jmp ($02FF)` run-exit thunk at `$C089` mapped to the `p6.exit` service.
- Translation: `TRANSLATED`, 262 instructions.
- Generated sources (`GENERATED`): host program sha256 `6c1ccac5...` (54198
  bytes) and MMC1 runtime support sha256 `c15980d4...` (640616 bytes), written
  deterministically to `generated/` in the caller workspace. Both identities
  are byte-identical to the frozen P6-07 emission record.
- Native build: `BUILT`, `EXECUTABLE_REPRODUCIBLE`, executable sha256
  `0ba034bd...` (identical to the frozen P6-08 record), clang-cl.exe /
  lld-link.exe, two independent build runs.
- Native execution: `EXECUTED`, three byte-identical runs, `failed=0`,
  `exit=1`, `steps=82731`, `pc=0xC089`, `frames=9`, `nmi=6`, `clock=241746`,
  `mmc1_regs=1F070703`, `mmc1_writes=5905`, `prg_ram_enabled=0`, transcript
  `0101010101010000` and the 9-frame transcript; all observables are
  byte-identical to the frozen P6-08 record. The original guest image is never
  executed on the host (`guest_code_executed_on_host=false`).
- Platform/runtime: `BOUNDED_NES_PLATFORM_MODEL_ACTIVE`; blockers `[]`;
  `stop_reason = "native execution reached"`.

## Fail-closed classification ledger

- Unsupported mapper (synthetic mapper-2 header): `FAIL_CLOSED`,
  `BLOCKED_UNSUPPORTED_MAPPER` / `unsupported_mapper`; translation, build and
  execution `NOT_ATTEMPTED`.
- Malformed image (truncated container): `FAIL_CLOSED`,
  `BLOCKED_UNSUPPORTED_CONTAINER` / `unsupported_container`, inventory
  `REJECTED`.
- Unsupported MMC1 variant (battery/PRG-RAM declaration):
  `FAIL_CLOSED`, `BLOCKED_UNSUPPORTED_MMC1_VARIANT` /
  `unsupported_mmc1_variant` with the exact reasons.
- Private local image (metadata/hash only): `SUPPORTED_MMC1` platform but
  `FAIL_CLOSED` translation with the exact recorded frontier:
  `BLOCKED_UNSUPPORTED_OPCODE` at `0xC570` (undocumented opcode `0x7C`, after a
  `jsr` at `0xC56D`, 1250 candidate instructions / 2711 bytes / 42 opcode
  forms / 202 fixed + 1048 power-on low window / 11 pending),
  `BLOCKED_UNRESOLVED_INDIRECT_CONTROL_FLOW` at `0x86E8`, `0x8956`, `0x8F3C`
  through `$E2`, `BLOCKED_BANK_STATE_UNRESOLVED` for the 1048 low-window
  candidates and `NOT_TESTED` platform/runtime. Generated sources, native
  build and native execution are `NOT_ATTEMPTED`; the public claim is `none`.
- Invocation errors fail closed without traceback: missing path, empty plan,
  out-of-range plan value, non-positive budget and non-positive native run
  count.

## Independent / reference comparison

- The frozen P6-09 independent MMC1 reference equivalence gate re-ran as a
  regression: `OPENRECOMP_P6_09=PASS`,
  `OPENRECOMP_PHASE6_MMC1_REFERENCE_EQUIVALENCE_V1=PASS tests=100`, exit 0,
  empty stderr, stdout sha256 raw `0144086e...` identical to the recorded
  P6-09 official capture.
- The workflow's generated identities and native observables are anchored to
  the committed P6-07/P6-08 evidence records (`anchor:p6-07-host-program`,
  `anchor:p6-07-support`, `anchor:p6-08-executable`,
  `anchor:p6-08-observables` all PASS).

## Negative / fail-closed coverage

The gate verifies 111 checks including the negative ledger above, the CLI
byte-identical stdout with empty stderr across runs, full-report and
analysis-report determinism across repeated workflow runs, no ROM-extension
file and no byte-identical ROM copy in the workflow workspace, and evidence
hygiene (no public proof ROM bytes and no private ROM bytes in any P6-12
evidence file).

## Regressions

- `tools/test_nes_rom_v1.py` (`PASS tests=12`), `tools/test_nes_platform_v1.py`
  (`PASS tests=10`), `tools/test_phase6_mmc1_inventory_v1.py`
  (`PASS tests=85`, stdout `2bfd8a5e...`), `tools/test_phase6_mmc1_variant_v1.py`
  (`PASS tests=61`, stdout `315fd5ea...`) and
  `tools/test_phase6_mmc1_reference_equiv_v1.py` (`PASS tests=100`, stdout
  `0144086e...`): all exit 0 with empty stderr (scratch evidence only; frozen
  committed evidence untouched). The recorded captures match the P6-11
  regression captures byte-for-byte.

## Claim ledger deltas

- New capability: a reusable deterministic ROM-to-native workflow for the
  bounded audited MMC1 subset, demonstrated end to end on the public proof
  fixture and fail-closed with explicit classifications elsewhere.
- The private TMNT frontier remains exactly as recorded at P6-10/P6-11: the
  same opcode, indirect-control-flow and bank-state blockers; no new platform,
  mapper, CPU or indirect semantics were added or promoted.
- Terminal marker remains `OPENRECOMP_PHASE6_MMC1_PLATFORM_PROOF=NOT_PROVEN`;
  general compatibility remains
  `OPENRECOMP_PHASE6_GENERAL_NES_COMPATIBILITY=NOT_PROVEN`.

## Limitations

- The workflow supports the bounded MMC1 subset and the public exact-size
  iNES/NES 2.0 containers only; NROM/mapper-0 is not routed through this
  workflow (the proven Phase-5 path remains separate).
- A translated ROM must expose a contiguous, fully documented fixed-bank code
  region and exactly the declared `$02FF` run-exit thunk; anything else fails
  closed.
- Extended PPU/APU/input/timing requirements beyond the bounded Phase-5/6
  platform model remain `NOT TESTED`.
- No general NES compatibility, no MMC1 board-variant coverage, no cycle or
  full PPU/APU accuracy, no FDS or arbitrary-6502 support is claimed.
- The private image remains without native execution or interactive
  behaviour; TMNT playability is not required and was not achieved.

## Repository side effects

- Tracked additive changes: new workflow module, new gate, manifest entries,
  updated control plane, P6-12 evidence. Scratch/build artifacts remain
  ignored; no ROM copy exists in the repository or evidence.

## Evidence index

`RESULT.md`, `p6_12_tests.json`, `official_runs.json`, `determinism.json`,
`workflow.json`, `blockers.json`, `anchors.json`, `regressions.json`,
`run1.txt`, `run2.txt`, `run1.err.txt`, `run2.err.txt`, `changed_files.txt`.

## Next stage

P6-13 - Second private TMNT compatibility run.
