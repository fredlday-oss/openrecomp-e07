# P2-20 — NES6502 program bridge V1

VERDICT: `PASS`

STAGE MARKER: `OPENRECOMP_P2_20=PASS`
GATE MARKER: `OPENRECOMP_NES6502_PROGRAM_BRIDGE_V1=PASS tests=86`

## Baseline

| Item | Value |
| --- | --- |
| Stage | `OPENRECOMP_P2_20_NES6502_PROGRAM_BRIDGE_V1` |
| Branch | `phase2/opencode-v1` |
| Starting commit | `2fc27bfd80ef36b62ab3dc854562bbb4d0ce82db` (`2fc27bf phase2: complete P2-14 larger MIPS32 open fixture`; `HEAD` at stage start) |
| Phase-1 freeze | tag `openrecomp-phase1-pass` -> `46c2f971e1a42cf49bd936bad94697b81bf31002` (unchanged) |
| Prior gates | P2-14 `82`, P2-13 `80`, P2-12 `96`, P2-11 `77`, P2-10 `108`, P2-09 `120`, P2-08 `169`, P2-07 `106`, P2-06 `134`, P2-05 `104`, P2-04 `61`, P2-03 `67`, P2-02 `82`, P2-01 `49` |

## Bounded acceptance contract

1. **Behavior proven**: a synthetic/original NES 6502 region can be fed through
   the **same** architecture-neutral Phase-2 persistent-program and
   translation-unit layers used by the MIPS32 path.
2. **Input**: one synthetic/original 15-instruction NES6502 region (26 bytes);
   no commercial ROM/game/BIOS bytes.
3. **Applicable stages**: P2-01 (ProgramModel), P2-02 (CFG), P2-03 (function
   discovery), P2-04 (call graph), P2-05 (translation units), P2-06
   (indirect-control-flow classification).
4. **Semantics exercised**: `ldx`, `clc`, `adc`, `sta abs,x`, `dex`, `bne`,
   `jsr`, `jmp abs`, `jmp (indirect)`, `nop`, `inx`, `rts`; a counted loop,
   an indexed store, a direct call/return pair, a direct jump, and an
   unresolved indirect jump whose target is a runtime value and is never
   inferred.
5. **Bridge seam**: `openrecomp/frontends/nes6502.py` is the only
   architecture-aware module; shared layers do not import any adapter,
   frontend, or architecture-specific code.
6. **Independent cross-check**: the executed instruction trace from the frozen
   Phase-1 `tools/nes6502_reference_v1.py` interpreter is a subset of the
   decoded instructions, and the executed control-flow instructions match the
   model exactly.
7. **Failure cases**: undocumented opcodes, truncated operand streams,
   out-of-range addresses, non-bytes memory images, empty regions, and
   entry-not-before-end all fail closed.
8. **Determinism**: two independent `bridge_program` calls produce byte-identical
   serializations and identical fingerprints for the program, CFG, function
   discovery, call graph, translation units and indirect-control-flow
   classification.
9. **Scope/non-claims**: proves only the structural program bridge for this
   bounded synthetic NES6502 region. It does not generate host code (P2-21),
   does not execute translated host code, and does not claim NES equivalence,
   compatibility, or whole-guest recompilation.

## Objective

Prove that the shared Phase-2 persistent-program and translation-unit layers
are not MIPS-specific by feeding a documented NES 6502 region through the same
layers.

## Files created/modified

| File | Change |
| --- | --- |
| `openrecomp/frontends/nes6502.py` | New P2-20 bridge: `bridge_region` / `bridge_program` / `NES6502Program`; maps `adapters.nes6502` decode results into the neutral `DecodedInstruction` / `ProgramModel` / CFG / function-discovery / call-graph / translation-unit / indirect-control-flow pipeline. |
| `tools/test_nes6502_program_bridge_v1.py` | New dedicated P2-20 gate (86 checks), with deterministic evidence output and Phase-1 reference cross-check. |
| `.openrecomp-phase2/evidence/P2-20/` | This evidence bundle. |
| `.openrecomp-phase2/{STATE,HANDOFF,STAGE_QUEUE}.md` | P2-20 PASS; P2-20 COMPLETE, P2-21 NEXT. |

No existing `openrecomp/*.py` implementation source was modified. The shared
pipeline layers are reused unchanged.

## Fixture

- architecture: `nes6502`, little-endian, 16-bit guest address space
- entry `0x8000`; region end `0x801A`; 15 decoded instructions, 26 bytes
- SHA-256 `0a236023c59fd5363d0ebdd6ffb18d9b4e792ebeaa11a72ca513b183539fa398`
- synthetic/original; assembled deterministically by a two-pass assembler inside
  the gate
- labels: `start=0x8000`, `loop=0x8002`, `bne=0x8009`, `call=0x800B`,
  `jmpd=0x800E`, `dispatch=0x8012`, `helper=0x8018`

Program shape:

```text
start:  ldx #$03
loop:   clc
        adc #$05
        sta $0400,x
        dex
        bne loop          ; loop 3 times
        jsr helper
        jmp dispatch
        nop
dispatch:
        jmp ($0300)       ; runtime target, never inferred
        nop
        nop
        nop
helper: inx
        rts
```

## Pipeline traversal

| Layer | Outcome |
| --- | --- |
| P2-01 ProgramModel | `ProgramSource` architecture=`nes6502`, adapter=`adapters.nes6502`, 15 `DecodedInstruction` objects with `adapter_fields` metadata. |
| P2-02 CFG | 8 blocks (`blk_8000`, `blk_8002`, `blk_800b`, `blk_800e`, `blk_8011`, `blk_8012`, `blk_8015`, `blk_8018`); loop back edge, call continuation, direct jump, unresolved indirect jump. |
| P2-03 functions | Two functions: `fn_8000` (entry, 5 blocks) and `fn_8018` (helper, 1 block); unowned blocks `blk_8011` and `blk_8015` preserved as residual evidence. |
| P2-04 call graph | Nodes `fn_8000`, `fn_8018`; one `INTERNAL_DIRECT` edge `fn_8000 -> fn_8018`. |
| P2-05 translation units | Two units: `tu_fn_8000`, `tu_fn_8018`; unowned blocks and unresolved sites preserved verbatim. |
| P2-06 classification | One site at `0x8012`: `UNRESOLVED_INDIRECT_JUMP`, basis `NONE`, no guessed targets. |

## Deterministic markers

- program fingerprint: `0dfbf094e667e61e298c28db9363e6b318bb60b595e6b2eb9249016b47a412e7`
- CFG fingerprint: `2924881e53cef31f6408a74abad5a7ff739c160870d7815a88bfc48a58960228`
- functions fingerprint: `7b83a827d3311d89961c3622d56f95f07bef83094de9771e0b0b82b7d5870d3f`
- call-graph fingerprint: `e99dce4ba85879cc6627b0d67a5f46aa5ead5007ca6c90004f2dbea5a4cfe370`
- translation-units fingerprint: `d0062fed1f2db5114cfbe2590f032cec844827f23f76310eba5e0fc97c7aa613`
- classification fingerprint: `67113cc118d04289ea7677802198509f80751342f9a4eeca2321c9e7a71e03de`
- gate stdout sha256: `d104147c5bbc176af44499aed94320e095350f8e9e7f6fafbab8667d33025f03`
- region bytes sha256: `0a236023c59fd5363d0ebdd6ffb18d9b4e792ebeaa11a72ca513b183539fa398`

## Independent/reference comparison

The frozen Phase-1 `tools/nes6502_reference_v1.py` interpreter ran the same
fixture memory image from entry `0x8000`:

- trace length: 21 executed instruction addresses
- all trace addresses are decoded instructions
- executed control-flow set equals the model control-flow set
- loop back edge taken 3 times (`trace.count(0x8002) == 3`)
- call order: `0x800B` before `0x8018` before `0x800E`
- final state: halted at `0x0202`, `a = 15`, `x = 1`

## Commands and exit codes

```text
python tools/test_nes6502_program_bridge_v1.py --evidence-dir .openrecomp-phase2/evidence/P2-20 --json .openrecomp-phase2/evidence/P2-20/p2_20_tests.json
OPENRECOMP_NES6502_PROGRAM_BRIDGE_V1_JSON=p2_20_tests.json
OPENRECOMP_NES6502_PROGRAM_BRIDGE_V1=PASS tests=86
exit 0
```

## Relevant Phase-1 and Phase-2 regressions

Phase-2 structural-layer gates (reused by the bridge) pass:

```text
OPENRECOMP_PROGRAM_MODEL_V1=PASS tests=49
OPENRECOMP_CFG_V1=PASS tests=82
OPENRECOMP_FUNCTION_DISCOVERY_V1=PASS tests=67
OPENRECOMP_CALL_GRAPH_V1=PASS tests=61
OPENRECOMP_TRANSLATION_UNITS_V1=PASS tests=104
OPENRECOMP_INDIRECT_CONTROL_FLOW_V1=PASS tests=134
```

MIPS32-specific end-to-end gates (P2-07..P2-14) pass unchanged:

```text
OPENRECOMP_HOST_EMITTER_V1=PASS tests=106
OPENRECOMP_GENERIC_RUNTIME_ABI_V1=PASS tests=169
OPENRECOMP_DETERMINISTIC_BUILD_V1=PASS tests=120
OPENRECOMP_MIPS32_END_TO_END_V1=PASS tests=108
OPENRECOMP_MIPS32_CALLS_MEMORY_V1=PASS tests=77
OPENRECOMP_MIPS32_DIRECT_CFG_V1=PASS tests=96
OPENRECOMP_RUNTIME_HOST_BOUNDARY_V1=PASS tests=80
OPENRECOMP_MIPS32_LARGER_FIXTURE_V1=PASS tests=82
```

Phase-1 NES6502 chain gates pass:

```text
OPENRECOMP_NES6502_STATE_V1=PASS tests=10
OPENRECOMP_NES6502_DECODE_V1=PASS
OPENRECOMP_NES6502_SEMANTICS_V1=PASS tests=102
OPENRECOMP_NES6502_LOWERING_V1=PASS tests=12
OPENRECOMP_NES_ROM_V1=PASS tests=12
OPENRECOMP_NES_PLATFORM_V1=PASS tests=10
OPENRECOMP_NES_HEADLESS_V1=PASS tests=7
```

Phase-1 host gates pass:

```text
python tools/phase1_host_gates_v1.py --json .openrecomp-phase2/evidence/P2-20/host_gates.json
OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
PASS source-integrity  verified 125 manifest entries
```

## Limitations

- The bridge is structural only; it does not lower to IR, emit host code, or
  execute translated code. P2-21 (NES6502 host emitter path) is queued.
- The fixture is a bounded synthetic 15-instruction region. It is not an
  iNES/NES 2.0 ROM, not a full NES program, and not a commercial guest.
- Indirect `jmp ($0300)` remains `UNRESOLVED_INDIRECT_JUMP`; the target is a
  runtime value and is never guessed.
- Only the documented official 6502 opcode set is supported; undocumented
  encodings fail closed through the adapter.
- `brk`, `rti`, and stack-resident returns are classified as control flow but
  are not exercised in this fixture; their behavior is covered in Phase-1.

## Repository side effects

- New untracked files: `openrecomp/frontends/nes6502.py`,
  `tools/test_nes6502_program_bridge_v1.py`,
  `.openrecomp-phase2/evidence/P2-20/`.
- No existing implementation source modified.
- `SOURCE_SHA256SUMS.txt` unchanged in this stage (the manifest covers existing
  tracked files; new files are outside its current scope).
- No commit created.

## Next stage

P2-21 — NES6502 host emitter path: generate host code for proven NES6502
semantics using the same `openrecomp/host_emitter.py` layer used by MIPS32.
Do not claim the final Phase-2 end-to-end marker.
