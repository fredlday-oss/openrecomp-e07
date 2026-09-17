# P3-05 result (PASS)

Stage: `P3-05` ProgramModel/CFG/functions/call graph/translation units on the
real ELF (frozen queue row).
Gate: `tools/test_phase3_structure_v1.py` (202 checks).
Evidence: `.openrecomp-phase3/evidence/P3-05/`.

Markers issued:

- Stage marker: `OPENRECOMP_P3_05=PASS`
- Gate marker: `OPENRECOMP_PHASE3_PROGRAM_STRUCTURE_V1=PASS tests=202`
- Terminal marker (reserved): `OPENRECOMP_PHASE3_REAL_ELF_RECOMP_PROOF=NOT_PROVEN`

## Scope

P3-05 exercises the frozen Phase-2 architecture-neutral structural layers on the
audited CoreMark MIPS32 reachable frontier:

- `openrecomp.program_model` (`DecodedInstruction`, `BasicBlock`,
  `FunctionUnit`, `ProgramModel`, `EvidenceClass`, `InstructionFlow`);
- `openrecomp.cfg` (`build_cfg`, `CLOSED` mode);
- `openrecomp.functions` (`discover_functions`);
- `openrecomp.call_graph` (`build_call_graph`);
- `openrecomp.translation_units` (`build_translation_units`).

No shared layer, no frozen adapter, no Phase-1/Phase-2 file and no root manifest
entry was modified. The Phase-3-only bridge is
`.openrecomp-phase3/src/p3_structure_v1.py`.

## Inputs and frontier cross-check

The fixture is the P3-01 ELF
(`16a0a0aa0f62344d8c0f309b755450f09c330e7c5a7c355785662d7a141f7669`,
31184 bytes, ELF32 little-endian `EM_MIPS` `ET_EXEC`, entry `0x4650`,
`.text` `0x1000` + 13948). The P3-03 frontier was re-derived from fresh bytes
and reproduced the recorded evidence exactly:

- 3487 words, 3479 decoded, 8 reserved, 0 unknown; 2178 reachable / 1309
  unreachable; reachability hash
  `c62d54838cbc5fcc7b0ff83cdc9b2f0f47b8851c5e4023ae2ca6d629c8f76edf`;
- reachable control flow: 198 conditional branches, 96 direct calls, 70 jumps,
  24 returns, 3 indirect jumps, 0 indirect calls, 0 unsupported control
  transfers; 391 delay slots;
- unresolved sites: three `jr $at` jump tables (`0x3130`, `0x3830`, `0x39a0`)
  and the branch-to-self boundary successor (`0x4674` not-taken -> `0x467c`
  outside the executable region);
- six reachable exception-frontier sites (`divu`/`teq`) unchanged;
- the dead `jalr` at `0x1958` and the eight `0x04170001` padding words stay
  unreachable.

## Structural result

Only `REACHABLE` records became neutral instructions; every instruction is a
4-byte `DecodedInstruction` with exact operands in metadata. Neutral flow is a
pure function of the frozen record:

| flow | count |
| --- | --- |
| NORMAL | 1787 |
| BRANCH | 198 |
| CALL | 96 |
| JUMP | 70 |
| RETURN | 24 |
| INDIRECT_JUMP | 3 |
| total | 2178 |

Shared-layer output (all PROVEN, see classification basis below):

- 615 basic blocks (518 owned + 97 orphan delay-slot blocks);
- 770 edges: 198 `BRANCH_TAKEN`, 198 `BRANCH_NOT_TAKEN`, 96 `CALL_RETURN`,
  205 `FALLTHROUGH`, 70 `JUMP`, 3 unresolved `INDIRECT`;
- 26 functions (entries pinned in `functions.json`);
- 96-edge direct call graph, all `INTERNAL_DIRECT`, no recursion, no external
  and no unresolved call edges;
- 26 translation units, entry unit `tu_fn_4650`; the three reachable `jr $at`
  sites stay attached to `fn_30b0` (`0x3130`) and `fn_371c` (`0x3830`,
  `0x39a0`) as unresolved jump sites with no invented target;
- fingerprints: program model
  `8ed487c0332977f2b5da2767ebc6a858020c5f8df9f049a30fbc026a099e5d94`, CFG
  `c9029a0d2382a9845f0da811dbbc343fe4d4573cc2cea6ac484f0d3fdc8ab814`, call
  graph `9462f40ccd7cd23bcedc37c03222335913d2da785696baf8cabb86fc5b4e93c9`,
  translation-unit set
  `44c8b895d7672d692b487c961ec448f655b1e0854639af706335f8760a9f3e25`,
  discovery `cf307c18bc925001e54edb678d83c5591d6e1e6af07435a91d7e17326c238e2f`.

### PROVEN classification basis

`EvidenceClass.PROVEN` here is the shared model's structural classification: an
exact decoded word reached from the proven ELF entry through resolved direct
edges. It is not a runtime-execution claim and not a semantics claim; P3-04
owns the semantic frontier and P3-08/P3-09 own execution. Indirect sites are
`unresolved` with no `direct_target`; the unresolved block edges carry evidence
about the edge's existence, never about a target.

### Delay-slot policy (explicit limitation)

The shared layers have no MIPS32 delay-slot concept. P3-05 represents delay
slots as ordinary NORMAL instructions and preserves the delay-slot relationship
separately in `cfg_structure.json` (`delay_slot_frontier`, 391 entries):

- a call delay slot is the `CALL_RETURN` continuation (96);
- a conditional-branch delay slot is the `BRANCH_NOT_TAKEN` successor (198);
- jump/return/indirect-jump delay slots (70 + 24 + 3 = 97) are explicit orphan
  blocks: reported in `unowned_blocks`, never attributed to a function, never
  given an invented predecessor and never executed implicitly. They are absent
  from the `ProgramModel` (2081 owned instructions) but present in the CFG
  (2178 instructions).

True delay-slot execution semantics remain in the P3-03/P3-04 frontier, the
P3-04 fail-closed semantics model and the later runtime stages.

## Verification

- 202 gate checks: source integrity (root manifest 134 entries frozen, Phase-3
  manifest 12 entries), fixture identity, exact P3-03/P3-04 cross-checks,
  neutral-instruction invariants, CFG invariants (every resolved edge matches
  its decoded target; every direct call continuation is the call's own delay
  slot; no direct target enters a delay slot), function/call-graph/translation
  unit invariants, serialization round-trips and the fail-closed negatives.
- 27 fail-closed negative/synthetic panels: rejected reserved encoding,
  unsupported control transfer, missing or forbidden targets, missing delay
  slot, inconsistent trap, duplicate record, non-tiling region, entry outside
  region, invalid source/entry/analysis, plus two synthetic positive programs.
- Determinism: two consecutive official runs are byte-identical (7819 bytes,
  raw sha256
  `12bf87d7b5ec57dcf637c940bfb0bfc483cd03c548291cbed21b9af9cbe29573`, LF sha256
  `f8948ea8ab651267d22c624bbb950fa0973c7fe82dd4f5f93606754ac60f7e39`, empty
  stderr, exit 0); a second isolated ingestion/frontier/structure build
  reproduces every fingerprint and artifact hash.
- Regressions (all exit 0, empty stderr, stdout byte-identical to their frozen
  captures): P2-99 `PASS tests=202` (`66913e57...`), P3-00 `PASS tests=61`
  (`a039bbff...`), P3-01 `PASS tests=76` (`81eede03...`), P3-02
  `PASS tests=197` (`f24f4cef...`), P3-03 `PASS tests=201` (`15e20a2c...`),
  P3-04 `PASS tests=126` (`412544a4...`), Phase-1 host gates
  `PASS=44 FAIL=0 SKIPPED=2` (`2a9d1bba...`), public safety `PASS`
  (`ad022ff1...`).
- Documented contract growth: the P3-02/P3-03/P3-04 gates' expected Phase-3
  manifest entry set grew additively from 10 to 12 (the new bridge module and
  this gate); all entries are still verified and their stdout is unchanged.

## Tracking boundary

The P3-05 boundary commits the Phase-3 control plane, sources, ports, gates and
the LF-normalized evidence (`P3-00` .. `P3-05` gate artifacts and P3-05
captures). Intentionally untracked: the external CoreMark sources, the
toolchain distribution, the build roots, and the 32 CRLF shell captures of the
earlier `P3-00` .. `P3-04` evidence (tracking them under the `*.txt`/`*.md`
LF-normalizing `.gitattributes` rule would change their bytes relative to the
raw stdout hashes recorded in their stage evidence). Their bytes stay on disk
and are hash-pinned by that evidence.

## Claim boundary

P3-05 proves only that the frozen Phase-2 structural layers run deterministically
on the audited CoreMark reachable frontier and that the direct structure is
recovered exactly. It does not translate or execute CoreMark, does not resolve
indirect targets, does not model true delay-slot execution semantics, and
claims no arbitrary MIPS32, PS1 or PS2 compatibility.
`COREMARK_STATUS=NOT_PROVEN`.
