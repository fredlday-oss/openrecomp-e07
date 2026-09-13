# P2-02 — Deterministic architecture-neutral CFG construction V1

VERDICT: `PASS`

STAGE MARKER: `OPENRECOMP_P2_02=PASS`
CFG GATE MARKER: `OPENRECOMP_CFG_V1=PASS tests=82`

## Baseline

| Item | Value |
| --- | --- |
| Stage | `OPENRECOMP_P2_02_CFG_CONSTRUCTION_V1` |
| Branch | `phase2/opencode-v1` |
| Starting commit | `a0c483029727168b1371aa9683e82900f9e14638` (P2-01 boundary; `HEAD` at start) |
| P2-00 boundary | `1b40269cc80cd19d49d8870f8e65aa1eced69885` |
| Phase-1 freeze | tag `openrecomp-phase1-pass` -> `46c2f971e1a42cf49bd936bad94697b81bf31002` (verified unchanged) |
| P2-01 gate | `OPENRECOMP_PROGRAM_MODEL_V1=PASS tests=49` (re-verified after this stage) |

Pre-flight: branch correct; `HEAD` equals the P2-01 boundary; the Phase-1 tag still
resolves to the frozen commit; starting `git status` showed only the excluded untracked
paths `.openrecomp-phase2/backups/`, `artifacts/mips32_translation_v1/`,
`artifacts/mips32_translation_evidence_closure_v1/` (left untouched).

## Files added

| File | Role |
| --- | --- |
| `openrecomp/cfg.py` | Neutral CFG/basic-block builder: `build_cfg`, `ControlFlowGraph`, `EntryPoint`, `CallSite`, `CFGMode`, `CFGError`, `combine_evidence`. |
| `tools/test_cfg_v1.py` | Deterministic 82-check CFG gate with optional `--json` record. |
| `.openrecomp-phase2/evidence/P2-02/*` | This evidence bundle. |

## Files modified

| File | Change |
| --- | --- |
| `openrecomp/program_model.py` | Backwards-compatible relaxation of `ProgramModel._validate_block`: unresolved successors are now permitted for any target-bearing edge kind (`FALLTHROUGH`, `BRANCH_TAKEN`, `BRANCH_NOT_TAKEN`, `JUMP`, `CALL_RETURN`, `INDIRECT`) provided they carry a `detail`; `RETURN`/`TRAP` may never be unresolved; an unresolved `INDIRECT_CALL` continuation is now allowed. Every previously valid model stays valid; no previously rejected state becomes silently accepted without a `detail`. Required by OPEN-mode CFG edges. |
| `SOURCE_SHA256SUMS.txt` | Registered `tools/test_cfg_v1.py` through the repository's `update_sums.py` (111 -> 112 entries). No existing hash changed. |
| `.openrecomp-phase2/STATE.md`, `HANDOFF.md` | Stage transition (P2-02 PASS -> P2-03). |

Frozen IR V1 (`ir_version = 1.0.0`), Module Image V1 (`1.0.0`), Core API, the AOT/native
ABI, and all Phase-1 adapters/frontends are untouched. No P2-01 test was weakened; the
full P2-01 suite still reports `tests=49`.

## CFG builder API

```python
build_cfg(instructions, *, source, entries, mode=CFGMode.CLOSED,
          region_boundaries=(), presorted=False) -> ControlFlowGraph
```

- `instructions`: any iterable of P2-01 `DecodedInstruction` (sorted internally; the
  supplied order is irrelevant unless `presorted=True`, which enforces ascending order).
- `source`: P2-01 `ProgramSource` (identity plus optional descriptive address width).
- `entries`: integer addresses or `EntryPoint(address, evidence, detail)`.
- `mode`: `CFGMode.CLOSED` or `CFGMode.OPEN`.
- `region_boundaries`: additional explicit block-start addresses.

`ControlFlowGraph` exposes `ordered_blocks()`, `ordered_entries()`, `block(id)`,
`predecessors()`, `to_program_model(region_id=None)`, `to_document()`, `serialize()`,
`deserialize()`, `fingerprint()`, and the call-site inventories
`direct_call_sites`, `unresolved_call_sites`, `unresolved_jump_sites`.

## Block-boundary algorithm

1. Normalize: reject duplicate addresses, enforce ascending order in `presorted` mode,
   reject overlapping extents and out-of-width addresses, and reject ambiguous flow
   (`NORMAL` + `unresolved`, `RETURN`/`TRAP` with a direct target).
2. Compute leaders from *evidence only*: explicit entries, region boundaries, every
   proven direct branch/jump/call target that lies in the supplied region, the
   instruction after a conditional branch or call continuation, and the instruction
   after a `RETURN`/`TRAP`/`INDIRECT_JUMP` when supplied instructions continue.
3. Single deterministic pass over ascending instructions: a block ends at a
   control-flow instruction, when the instruction's computed extent
   (`address + size_bytes`) does not meet the next supplied instruction, or when the
   next instruction is a leader. Blocks partition the input exactly.

No architecture fact is used: boundaries come from supplied metadata and
`DecodedInstruction.size_bytes`, never from `address + 4`, delay slots or fixed widths.

## Edge-generation algorithm

| Terminal flow | Edges produced |
| --- | --- |
| `NORMAL` (block ends at a leader/region end) | one `FALLTHROUGH` to the next instruction when it is supplied; otherwise none (region end) |
| `BRANCH` | `BRANCH_TAKEN` to the proven target (or an explicit unresolved edge when the target is computed/absent) + `BRANCH_NOT_TAKEN` to the continuation |
| `JUMP` | exactly one `JUMP` to the proven target (resolved or explicit unresolved) |
| `CALL` | exactly one `CALL_RETURN` to the continuation; the callee target is recorded as a `CallSite` and never absorbed as an edge |
| `INDIRECT_CALL` | exactly one `CALL_RETURN` continuation + an `UnresolvedSite`; no direct-call edge |
| `INDIRECT_JUMP` | exactly one unresolved `INDIRECT` edge + an `UnresolvedSite`; no speculative edges |
| `RETURN` / `TRAP` | none |

Backward branch/jump targets form ordinary resolved edges (self-loops and cross-block
cycles are represented and validated).

## Call handling

A direct call records `CallSite(block, address, op, target, evidence)` and creates only
the `CALL_RETURN` continuation edge. `ControlFlowGraph.direct_call_sites` is the
direct-call inventory; `unresolved_call_sites` holds computed call sites. Callee blocks
exist only when the callee is independently supplied (e.g. as an entry/region
boundary); there is no function discovery and no caller CFG absorption.

## Indirect-flow handling

Indirect jumps/calls terminate the block with an explicit unresolved successor
(`resolved=False`, no `target_block`, `detail` set) and are inventoried in
`unresolved_jump_sites` / `unresolved_call_sites`. No target is invented and no edge is
added speculatively. Computed branches (`BRANCH` with no `direct_target`) produce an
unresolved `BRANCH_TAKEN`.

## Closed/open CFG policy

- **CLOSED** (default): every direct *local* edge (branch/jump target and every required
  fallthrough) must resolve to a supplied instruction; a missing/out-of-region local
  target is rejected. A direct *call* target is allowed to be external (it is not a local
  edge) and is only recorded as a `CallSite`.
- **OPEN**: an edge that leaves the supplied decoded region becomes an explicit
  unresolved edge carrying its destination `target_address` and a `detail`; nothing is
  discarded. Missing closed targets are still never silently dropped.

Both modes are tested (including an external branch target and external fallthrough).

## Evidence propagation rules

- `combine_evidence(...)` is `PROVEN` only if every input is `PROVEN`, else `CANDIDATE`.
- A block's evidence joins its member instructions' evidence and, for an entry block,
  the supplied `EntryPoint.evidence`.
- An edge's evidence joins the source block/instruction evidence and the target block
  evidence.
- Deterministic processing never strengthens evidence: a `CANDIDATE` input yields
  `CANDIDATE` blocks/edges; classifications survive serialize/deserialize.

## Address-width handling

Addresses are arbitrary-precision Python integers and are stored in JSON as integers
(no truncation). `ProgramSource.address_width_bits` is optional and descriptive: when
present it is used only to reject out-of-width addresses. A test builds a CFG at
`0x1_0000_0000` and verifies entry and branch-target addresses above `0xFFFFFFFF`.

## Architecture-neutrality analysis

`openrecomp/cfg.py` imports only P2-01 neutral types and contains no ISA knowledge (no
opcode tables, no fixed width, no `address + 4`, no delay slots, no endianness, no
memory map, no ROM/ELF/PE/XBE handling, no console or backend). Instruction extent is
read from `DecodedInstruction.size_bytes`; ordering, width and flow are supplied by the
caller. The model is exercised with a 64-bit synthetic guest and a real 16-bit NES 6502
stream, both through the same code path. The CFG container wraps into the P2-01
`ProgramModel` via `to_program_model()` purely as a validation/serialization bridge, not
as function discovery.

## Fail-closed validation rules

Builder/container rejections (all raise `CFGError`, never repaired heuristically):

1. duplicate instruction addresses;
2. overlapping instruction extents;
3. non-positive / unavailable instruction extent where a fallthrough is required;
4. malformed direct target (out-of-width, interior, malformed entry point/boundary);
5. direct local target missing in CLOSED mode;
6. impossible fallthrough (branch/call extent unavailable);
7. fallthrough into the middle of another instruction;
8. branch/direct target into the middle of another instruction;
9. duplicate block identity;
10. overlapping block entry/ownership;
11. instruction assigned to more than one block;
12. block containing a control-flow instruction before its terminator;
13. edge referring to a nonexistent local block;
14. malformed entry point (not a supplied instruction);
15. entry point into the middle of an instruction;
16. nondeterministic construction (prevented by canonical ordering; asserted by tests);
17. inconsistent supplied ordering/address identity (`presorted` mismatch);
18. ambiguous flow that cannot be represented faithfully (`NORMAL` + `unresolved`,
    `RETURN`/`TRAP` with a target);
19. instruction not assigned to any block;
20. output of `to_program_model()` re-validated by the P2-01 `ProgramModel` validator.

## Test inventory (82 checks)

1.  straight-line sequence -> one block (membership, terminal);
2.  conditional branch -> target and fallthrough;
3.  forward conditional branch (target/fallthrough addresses, predecessor);
4.  backward conditional branch / loop (self edge, self predecessor);
5.  unconditional forward jump (single jump edge, no fallthrough);
6.  unconditional backward jump (self edge);
7.  return terminator (no successor);
8.  direct call with continuation (CALL_RETURN, call-site record, callee not absorbed);
9.  direct call target kept separate (local callee block, no edge to callee);
10. unresolved indirect call (continuation + unresolved site, no direct site);
11. unresolved indirect jump (single unresolved edge + site);
12. terminal/stop `TRAP` (no successor);
13. multiple branch targets across one region;
14. multiple explicit entry points;
15. disconnected decoded regions;
16. variable-width instruction sequence (extent-derived boundaries);
17. real NES6502 adapter-derived variable-width decode (3 blocks, branch edges, sizes, PROVEN);
18. address `> 0xFFFFFFFF` (entry and target preserved);
19. deterministic block ordering;
20. deterministic edge ordering;
21. deterministic serialization/fingerprint and round-trip;
22. PROVEN preservation (block + edges);
23. CANDIDATE preservation (block + edges not promoted; `combine_evidence`);
24. duplicate instruction rejection;
25. overlapping extent rejection;
26. direct target into instruction interior rejection;
27. fallthrough into instruction interior rejection;
28. missing CLOSED target rejection;
29. malformed entry-point rejection;
30. edge-to-nonexistent-local-block rejection;
31. instruction-after-terminal inconsistency rejection;
32. unsupported/ambiguous-flow fail-closed;
33. open-mode external branch target and external fallthrough;
34. region boundary splitting;
35. duplicate block identity / overlapping entry / instruction in two blocks / unassigned instruction;
36. `presorted` inconsistency, entry interior, `RETURN` with target, impossible call fallthrough, malformed boundary;
37. schema validation of `to_program_model()` for four CFGs; CLI validator acceptance;
38. CFG document round-trip preserving unresolved sites and fingerprint.

## Test result counts

```text
python tools/test_cfg_v1.py
OPENRECOMP_CFG_V1=PASS tests=82
```

82 checks, 0 failures.

## Deterministic repeated-run comparison

```text
run 1 == run 2 stdout (byte-identical)
stdout sha256 = 483df98e4ecb6a64441d22692ddcd54777ec52956dc041dae44242cb32886e70
```

Block boundaries, block identities, edge ordering, serialization and fingerprints are
identical across runs and independent of input order (a reversed instruction list
serializes byte-identically).

Sample fingerprints:

```text
forward_branch c0cea9ede69ce637c53c86b08fa48c96aa4d0746f1fc33c6b24795231338389a
nes6502        ec75d3886ff218fd2e1f2f7bc88b6a30f7e54e87585c04a381c5d4770ea9a554
wide           924c6f5f6373846bc80aa225149e023b382787eeeb64d408043d71cd4f10e62f
open_external  a220a642e8cbd1b3ff40e791ee537ea3b62276d7833e65af99e455afd651e68c
```

## P2-01 regression result

```text
python tools/test_program_model_v1.py
OPENRECOMP_PROGRAM_MODEL_V1=PASS tests=49
```

The only P2-01 change is the backwards-compatible unresolved-successor relaxation
documented above; all 49 P2-01 checks still pass and frozen IR V1 is untouched.

## Phase-1 regression result

```text
python tools/phase1_host_gates_v1.py --json .openrecomp-phase2/evidence/P2-02/host_gates.json
OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
```

Same 44 PASS / 0 FAIL / 2 toolchain skips (`e07-hardened-end-to-end`,
`external-repro-v1`) as the P2-00/P2-01 baselines; no unexpected change.

## Source-integrity result

```text
python tools/phase1_host_gates_v1.py --only source-integrity
PASS source-integrity  verified 112 manifest entries
```

`SOURCE_SHA256SUMS.txt` gained exactly one entry (`tools/test_cfg_v1.py`) via
`update_sums.py`; no existing hash changed.

## Deterministic artifacts

| Artifact | SHA-256 |
| --- | --- |
| `cfg_tests.json` | `c6ec61813448b4854e92c7b6c38f643e2990ead7056cbb79a9f97b41d4345fde` |
| `cfg_tests.txt` (UTF-8) | `483df98e4ecb6a64441d22692ddcd54777ec52956dc041dae44242cb32886e70` |
| `host_gates.json` | `a53e934d06b0f73eaa4903ab5ce9d521990149657de82ea82325a23ec16c5fb1` |
| `host_gates.txt` (UTF-8) | `16d08f090aba74043755cdcec3e3f10f84728d43890b638454d03abbadf9de90` |
| `sample_cfg.json` (CFG document) | `ec75d3886ff218fd2e1f2f7bc88b6a30f7e54e87585c04a381c5d4770ea9a554` |
| `sample_cfg.program.json` (P2-01 ProgramModel view) | `dfbd9dbe4be4f4418726ac6d0b0914cba7e3c8bf29e9cc86ae7d2a9e1e897744` |
| `openrecomp/cfg.py` | `27b5778428305a7948be50ee74ddc8f19ac1907c0a7b3ce980490d99ac6b5159` |
| `openrecomp/program_model.py` | `0bd72d55e6a76de0d96c266a85fb4a0ebebb06e940f09dff1337f1392d7f0cb1` |
| `tools/test_cfg_v1.py` | `969cac9ccd00385f41f682fdafd26f7348789c061f5a5f961ce3576da99b1cfc` |

Text evidence is UTF-8 without BOM.

## Schema

No P2-01 schema change was required. The CFG container uses its own canonical
document (`cfg_version = "1.0.0"`) validated in Python, and its P2-01
`ProgramModel` view (`to_program_model()`) validates against the existing
`schema/openrecomp-program-v1.schema.json` and `tools/validate_program_model_v1.py`
(both exercised by the tests).

## Known limitations

- No function discovery, whole-program call graph, jump-table recovery or indirect
  resolution; call callees are not blocks unless independently supplied.
- The CFG is a structural artifact; no instruction semantics, IR lowering or runtime.
- `schema/*.json` and `openrecomp/*.py` remain outside `SOURCE_SHA256SUMS.txt`
  (pre-existing `schemas/` glob gap in `update_sums.py`), so `openrecomp/cfg.py` and the
  `program_model.py` change are not integrity-manifest tracked; they are covered by the
  test suite and recorded hashes here.
- The `fallthrough-into-interior` scenario is necessarily accompanied by an extent
  overlap in an ordered non-overlapping input; both are rejected (the interior-specific
  guard runs first), and the overlap guard covers the remainder.
- Toolchain-gated Phase-1 gates remain skipped on this host.

## Explicit non-claims

P2-02 does **not** claim automatic function discovery, whole-program recovery, a complete
call graph, resolved indirect calls, jump-table recovery, architecture-independent
instruction semantics, PS2/Xbox compatibility, complete NES compatibility, game
compatibility, generic runtime support, or RT64 integration. The NES6502 validation is a
bounded decoder-driven structural test, not general NES program recovery.

## Recommended P2-03 frontier

Function recovery on top of this CFG: entry/function ownership over the neutral
`ControlFlowGraph`, explicit unknown/unresolved regions, and a direct-call graph built
from `direct_call_sites` (direct calls only; unresolved indirect calls kept separate),
keeping heuristics `CANDIDATE` and failing closed on ambiguity.

## Final verdict

`PASS` — deterministic, architecture-neutral basic-block and CFG construction exists on
the P2-01 shared model, with 82 deterministic checks, 44 Phase-1 gates green, the P2-01
suite green, and source integrity verified.
