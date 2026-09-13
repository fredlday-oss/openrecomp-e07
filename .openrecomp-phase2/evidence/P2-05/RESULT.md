# P2-05 — Deterministic architecture-neutral translation units V1

VERDICT: `PASS`

STAGE MARKER: `OPENRECOMP_P2_05=PASS`
GATE MARKER: `OPENRECOMP_TRANSLATION_UNITS_V1=PASS tests=104`

## Baseline

| Item | Value |
| --- | --- |
| Stage | `OPENRECOMP_P2_05_TRANSLATION_UNITS_V1` |
| Branch | `phase2/opencode-v1` |
| Starting commit | `ea954d6306352fe63ed438cc43f107fe168471d4` (`ea954d6 phase2: complete P2-04 call graph recovery`; `HEAD` at start) |
| Prior boundary | P2-04 `ea954d6306352fe63ed438cc43f107fe168471d4` |
| Phase-1 freeze | tag `openrecomp-phase1-pass` -> `46c2f971e1a42cf49bd936bad94697b81bf31002` (verified unchanged) |
| Prior gates | P2-04 `61`, P2-03 `67`, P2-02 `82`, P2-01 `49` |

Pre-flight: branch correct; `HEAD` equals the expected P2-04 boundary; the Phase-1 tag
still resolves to the frozen commit; starting `git status` showed only the excluded
untracked paths `.openrecomp-phase2/backups/`, `artifacts/mips32_translation_v1/`,
`artifacts/mips32_translation_evidence_closure_v1/` (left untouched).

## Objective

Package each P2-03 discovered `FunctionUnit`, together with its P2-02 CFG structure and
P2-04 direct-call evidence, into exactly one deterministic `TranslationUnit` suitable for
later translation/lowering stages. P2-05 is a **structural packaging boundary**: it must
not perform IR lowering and must not invent control-flow/call targets.

## Files added

| File | Role |
| --- | --- |
| `openrecomp/translation_units.py` | Neutral translation-unit layer: `TranslationUnit`, `TranslationUnitSet`, `build_translation_units`, `build_translation_units_from`, `TranslationUnitError`. |
| `tools/test_translation_units_v1.py` | Deterministic 104-check P2-05 gate with optional `--json` record. |
| `.openrecomp-phase2/evidence/P2-05/*` | This evidence bundle. |

## Files modified

| File | Change |
| --- | --- |
| `SOURCE_SHA256SUMS.txt` | Registered `tools/test_translation_units_v1.py` via `update_sums.py` (114 -> 115 entries). No existing hash changed. |
| `.openrecomp-phase2/STATE.md`, `HANDOFF.md` | Stage transition (P2-05 PASS -> P2-06). |

No P2-01/P2-02/P2-03/P2-04 source was modified. Frozen IR V1 (`ir_version = 1.0.0`),
Module Image V1 (`1.0.0`), Core API, the AOT/native ABI, the CFG builder, function
discovery and the call graph are untouched. No prior test was weakened.

## Public API

```python
build_translation_units(discovery: FunctionDiscoveryResult, *,
                        call_graph: CallGraph | None = None) -> TranslationUnitSet
build_translation_units_from(cfg: ControlFlowGraph, functions, *,
                             provenance=None, suppressed_entries=(),
                             shared_blocks=(), unowned_blocks=(),
                             external_direct_call_targets=(),
                             entry_function_id, call_graph=None) -> TranslationUnitSet
```

`TranslationUnit` exposes `unit_id`, `function_id`, `entry_address`, `blocks`,
`call_edges`, `direct_callees`, `unresolved_call_sites`, `unresolved_jump_sites`,
`evidence`, `entry_sources`, `provenance`, plus `instructions()`, `block(id)`,
`to_document()` and `from_document()`.

`TranslationUnitSet` exposes `units`, `source`, `entry_unit`, `shared_blocks`,
`suppressed_entries`, `unowned_blocks`, `external_direct_call_targets`,
`unowned_control_flow`, plus `ordered_units()`, `unit_for(function_id)`,
`unit_by_id(unit_id)`, `function_ids()`, `to_document()`, `serialize()`,
`fingerprint()`, `from_document()` and `deserialize()`.

## FunctionUnit -> exactly one TranslationUnit

`build_translation_units` derives one unit per P2-03 `FunctionUnit` with
`unit_id = "tu_" + function.id`; ids are stable P2-03 function ids, so the mapping is
one-to-one, bijective and reproducible. `TranslationUnitSet` rejects duplicate unit ids,
duplicate function ids, duplicate entry addresses and empty input, so exactly one unit
per function is enforced structurally.

## Required-semantics mapping

1. **One TU per FunctionUnit** — one unit built per discovered function; set validation
   rejects duplicates/missing.
2. **Identity + arbitrary-width addresses** — `function_id`, `entry_address` (arbitrary
   precision `int`) and every instruction/target address are preserved verbatim; a
   64-bit (`0x1_0000_0000`) and a >64-bit (`0x1_0000_0000_0000_0000`) fixture round-trip
   byte-identically.
3. **Deterministic block ordering** — `_canonical_blocks` places the entry block first,
   then orders remaining blocks by `(entry_address, block.id)` (matching P2-01
   `FunctionUnit.canonical_blocks`). Construction is input-order independent.
4. **All instructions preserved** — units carry the original `BasicBlock` objects, so
   every `DecodedInstruction` is preserved exactly (objects and order), never rewritten.
5. **Resolved direct calls preserved** — each unit carries the P2-04 call edges whose
   caller is that function; `direct_callees` is reconciled with the resolved
   `INTERNAL_DIRECT` edges and validated against both P2-01 and P2-04.
6. **Unresolved/indirect evidence preserved** — `UNRESOLVED_INDIRECT` call edges,
   `FunctionUnit.unresolved_call_sites`, and CFG `unresolved_jump_sites` owned by the
   function's blocks are retained with their original reason/evidence. External direct
   calls keep their exact `target_address` and never receive a callee. No target is
   invented.
7. **Provenance/evidence** — each unit carries `evidence`, `entry_sources` and the P2-03
   `EntryBasis` provenance; the set carries `shared_blocks`, `suppressed_entries`,
   `unowned_blocks` and `external_direct_call_targets` so a unit can always be explained.
8. **Byte-identical determinism** — canonical JSON via `canonical_json`; `serialize()`
   and `fingerprint()` are byte/fingerprint stable across repeated construction and
   round-trip. See `determinism.txt`.
9. **Fail closed** — `TranslationUnitError` (never heuristic repair) on structurally
   invalid or unsupported input.
10. **No IR lowering** — the module imports only neutral P2-01/P2-02/P2-03/P2-04 types;
    it exposes no lowering/emit API and the serialized form contains no IR keys. The
    frozen IR V1 / Module Image V1 are untouched.
11. **No architecture-specific assumptions** — no opcode table, calling convention, link
    register, delay slot, stack frame, fixed width, endianness or console rule. The same
    code path handles synthetic 32/64/>64-bit and 16-bit NES6502-derived input.
12. **No discarded retained evidence** — `unowned_blocks` and control flow in unowned
    blocks are retained at set level (`unowned_control_flow`) instead of dropped.

## Unresolved-jump ownership

`cfg.unresolved_jump_sites` are mapped to units by exact P2-03 block ownership. A jump
site in an owned block is attached to that unit; a jump/call site in a block owned by no
function is preserved in `TranslationUnitSet.unowned_control_flow` rather than discarded.
`TranslationUnitSet` rejects an `unowned_control_flow` site whose block is actually owned,
and rejects an owned-site reference to an unowned block.

## Evidence propagation rules

- Unit evidence = P2-03 `FunctionUnit.evidence`.
- `call_edges` evidence = the P2-04 edge evidence (`INTERNAL_DIRECT` edges already combine
  call-site with callee-node evidence).
- Unresolved call/jump site evidence = the P2-02/P2-03 site evidence.
- `CANDIDATE` is never promoted; classifications survive serialization/deserialization.

## Deterministic serialization / fingerprint

`TranslationUnitSet.to_document()` emits `translation_unit_set_version = "1.0.0"`,
`source`, `entry_unit`, `units` (ordered by `(entry_address, function_id)`),
`shared_blocks`, `suppressed_entries`, `unowned_blocks`, `external_direct_call_targets`
and `unowned_control_flow`. Each unit emits `unit_id`, `function_id`, `entry_address`,
`evidence`, `entry_sources`, `provenance`, sorted `direct_callees`, canonical `blocks`,
sorted `call_edges`, and sorted unresolved call/jump sites. `serialize()` is canonical
JSON; `fingerprint()` is its SHA-256.

```text
two consecutive P2-05 gate runs: byte-identical stdout
run stdout sha256 = 7209c6ff6bc40d131af0e04eae3c48d48d785ce864de46d0e406d81dbdbbc24a
```

Sample `TranslationUnitSet` fingerprints:

```text
single   bcce624595e3e69ec5b5d1d210147fb265e15b4d92af2fc6f7b38838f4b5ba71
calls    400c54cc1b30c0105650f955c08f931ce3838cac23469e90aac412e9270d0e17
shared   3d69309ebe040deaf742b7b7906ab80d623a600635b6f9ca8e1c3cdc648068a4
unowned  b15808062a0c3ab16be113a93168cc4746097ac9f50a445cbf5fea8d653f0a2c
wide     30d604963ef9c303c7b2d61a5ac9de99440311abea87c2b2ed9ec405d3fe832c
nes6502  b3541a1985add016a39fdf7be50b1e0db05cbb72306606f21000f41b23234f81
```

## Tests / coverage

```text
python tools/test_translation_units_v1.py
OPENRECOMP_TRANSLATION_UNITS_V1=PASS tests=104
```

Coverage: deterministic construction, one-to-one mapping, stable/input-independent
ordering, verbatim instruction and CFG/block/successor preservation, resolved direct
calls (per-site + `direct_callees`), unresolved indirect calls, external direct calls
with no invented callee, indirect-jump preservation, provenance/`entry_sources`,
candidate non-promotion, shared-block/suppressed/unowned/external residual preservation,
64-bit and >64-bit addresses, canonical serialization and round-trip byte identity,
cross-checks against the P2-01 `ProgramModel.direct_call_graph()` and the P2-04
`CallGraph`, a bounded NES6502-derived unit set, absence of any IR lowering, and all
fail-closed rejections below.

## Fail-closed behavior

`TranslationUnitError` (never heuristic repair) for:

1. a non-`FunctionDiscoveryResult` discovery, a non-`CallGraph` call graph, or an empty
   function list;
2. a call graph whose nodes do not match the discovered functions (id/entry/evidence), or
   whose source disagrees with the CFG;
3. a block owned by more than one function;
4. a unit with no blocks, or whose entry address matches no owned block;
5. a call edge whose caller is not the unit's function or whose site block is not owned;
6. `direct_callees` disagreeing with the unit's resolved call edges;
7. an unresolved call/jump site whose block is not owned by the unit;
8. set-level duplicate unit id, function id or entry address; empty unit set;
9. an `entry_unit` that is not a unit;
10. `unowned_blocks` overlapping owned blocks, or an `unowned_control_flow` site whose
    block is owned;
11. a shared block that is not owned or names an unknown owner;
12. a suppressed entry naming an unknown owner;
13. an external direct-call target equal to a unit entry;
14. an entry address exceeding the declared address width;
15. malformed JSON, a non-object document, an empty unit block list, or an unsupported
    `translation_unit_set_version`;
16. unknown unit/function lookups.

## Regression gates

```text
OPENRECOMP_TRANSLATION_UNITS_V1=PASS tests=104
OPENRECOMP_CALL_GRAPH_V1=PASS tests=61
OPENRECOMP_FUNCTION_DISCOVERY_V1=PASS tests=67
OPENRECOMP_CFG_V1=PASS tests=82
OPENRECOMP_PROGRAM_MODEL_V1=PASS tests=49
OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
PASS source-integrity  verified 115 manifest entries
```

The two toolchain-gated Phase-1 gates (`e07-hardened-end-to-end`,
`external-repro-v1`) remain unexecutable on this host (missing `gcc`, `posix`) and are
never counted as pass.

## Architecture-neutrality assessment

`openrecomp/translation_units.py` imports only P2-01/P2-02/P2-03/P2-04 neutral types.
It contains no ISA knowledge: no opcode table, calling convention, link register, delay
slot, stack frame, fixed/variable width, endianness, address-width or console
assumption. Addresses are arbitrary-precision integers. The same code path handles
32-bit synthetic, 64-bit synthetic, >64-bit synthetic and 16-bit NES6502-derived input.

## Stage-naming note

The repository `STAGE_QUEUE.md` row for P2-05 is labelled "Indirect-control-flow
classification" and the translation-unit model is listed under P2-06. This execution was
explicitly directed as `OPENRECOMP_P2_05_TRANSLATION_UNITS_V1`, so P2-05 was implemented
as the deterministic translation-unit packaging stage. No control document was
restructured; `STAGE_QUEUE.md` is intentionally left unchanged and this deviation is
recorded here and in `STATE.md`/`HANDOFF.md`.

## Deterministic artifacts

| Artifact | SHA-256 |
| --- | --- |
| `openrecomp/translation_units.py` | `21b6021442fc2c48532dcd6c03b55ff70c8993a8b199ec5ada07fa5108b5346f` |
| `tools/test_translation_units_v1.py` | `fb7e0a72a5a437ac3b0bc3970cffe6290025be79b521ff100df24d80803a0f98` |
| `translation_units_tests.json` | `c68226fa94b07bd7606ce7695769d42411a29380cffa85050489f6f80d462412` |
| `translation_units_tests.txt` (UTF-8) | `4e853f379806fbfa848eb28066f9db56be036ab5aaf518aa70b216f53ee3f70c` |
| `host_gates.json` | `cc05d29338aa98cf00880477ffb687f5483a840c483b5e354265d6e1c832cc3b` |
| `host_gates.txt` (UTF-8) | `c70e826746f64223022514c6393069e4dc713dcfbf28b25db28497cb8812d259` |

Text evidence is UTF-8 without BOM.

## Known limitations

- A translation unit is a structural package; it is not a lowered/emitted artifact.
- `direct_callees` remain provisional P2-01/P2-03 structural facts, not ABI recovery.
- Indirect calls remain unresolved and indirect jumps are retained as evidence only;
  no jump-table or indirect-target recovery is performed.
- `schema/*.json` and `openrecomp/*.py` remain outside `SOURCE_SHA256SUMS.txt`
  (pre-existing `update_sums.py` `schemas/` glob gap); the new files are covered by the
  hashes above.
- Toolchain-gated Phase-1 gates remain skipped on this host.

## Explicit non-claims

P2-05 does **not** claim IR lowering, host emission, AOT integration, indirect/jump-table
target recovery, calling-convention/ABI recovery, whole-program function recovery beyond
the supplied region, whole-game recompilation, console compatibility, generic runtime
support or RT64 integration. The NES6502 validation is a bounded structural test.

## Next stage

`CURRENT_STAGE = P2-06`. P2-06 implementation was **not** started. The next agent should
confirm the exact P2-06 definition against the controlling stage prompt, because the
`STAGE_QUEUE.md` label lags the executed P2-05 directive (see the stage-naming note).

## Final verdict

`PASS` — a deterministic, architecture-neutral, one-to-one translation-unit packaging
layer now exists over the P2-03 functions, P2-02 CFG and P2-04 call graph, with no
lowering, no invented targets, reproducible serialization, and all upstream and Phase-1
regressions green.

OPENRECOMP_P2_05=PASS
OPENRECOMP_TRANSLATION_UNITS_V1=PASS tests=104
