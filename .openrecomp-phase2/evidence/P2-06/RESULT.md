# P2-06 â€” Deterministic architecture-neutral indirect-control-flow classification V1

VERDICT: `PASS`

STAGE MARKER: `OPENRECOMP_P2_06=PASS`
GATE MARKER: `OPENRECOMP_INDIRECT_CONTROL_FLOW_V1=PASS tests=134`

## Baseline

| Item | Value |
| --- | --- |
| Stage | `OPENRECOMP_P2_06_INDIRECT_CONTROL_FLOW_CLASSIFICATION_V1` |
| Branch | `phase2/opencode-v1` |
| Starting commit | `ce9cd4fc3aa87cbe9009c39abd52c5de083080e1` (`ce9cd4f phase2: complete P2-05 translation units`; `HEAD` at stage start) |
| Phase-1 freeze | tag `openrecomp-phase1-pass` -> `46c2f971e1a42cf49bd936bad94697b81bf31002` (verified unchanged) |
| Prior gates | P2-05 `104`, P2-04 `61`, P2-03 `67`, P2-02 `82`, P2-01 `49` |
| Pre-existing tree state | Documentation-only queue reconciliation edits to `STATE.md` / `HANDOFF.md` / `STAGE_QUEUE.md` were already uncommitted at stage start (P2-05 boundary `ce9cd4f` remained `HEAD`); preserved and extended. |

Pre-flight: branch correct; `HEAD` equals the P2-05 boundary; Phase-1 tag resolves to the
frozen commit; only the excluded untracked residue (`.openrecomp-phase2/backups/`,
`artifacts/mips32_translation_v1/`, `artifacts/mips32_translation_evidence_closure_v1/`)
was present and was left untouched.

## Objective

Classify every supported indirect-control-flow site carried forward by the completed
structural pipeline (P2-01 program model â†’ P2-02 CFG â†’ P2-03 functions â†’ P2-04 call graph
â†’ P2-05 translation units) into an explicit, deterministic, fail-closed category. Unknown
targets must remain unknown; no target may be inferred from address-shaped data, nearby
code, opcode appearance or adapter metadata. No IR lowering and no host emission.

## Files added

| File | Role |
| --- | --- |
| `openrecomp/indirect_control_flow.py` | Neutral P2-06 classifier: `IndirectControlFlowKind`, `IndirectControlFlowStatus`, `IndirectControlFlowBasis`, `IndirectControlFlowEvidence`, `IndirectControlFlowClassification`, `IndirectControlFlowUnit`, `IndirectControlFlowSet`, `classify_indirect_control_flow`, `classify_indirect_control_flow_from`, `IndirectControlFlowError`. |
| `tools/test_indirect_control_flow_v1.py` | Deterministic 131-check gate with optional `--json` record. |
| `.openrecomp-phase2/evidence/P2-06/*` | This evidence bundle. |

## Files modified

| File | Change |
| --- | --- |
| `SOURCE_SHA256SUMS.txt` | Registered `tools/test_indirect_control_flow_v1.py` via `update_sums.py` (115 -> 116 entries). No existing hash changed. |
| `.openrecomp-phase2/STATE.md`, `HANDOFF.md` | Stage transition (P2-06 PASS -> P2-07). |
| `.openrecomp-phase2/STAGE_QUEUE.md` | Control-plane status only: P2-06 `COMPLETE`, P2-07 `NEXT`. |

No P2-00..P2-05 implementation source or evidence was modified. Frozen IR V1
(`ir_version = 1.0.0`), Module Image V1 (`1.0.0`), Core API, the AOT/native ABI, the CFG
builder, function discovery, the call graph and the translation-unit layer are untouched.
No prior test was weakened.

## Public API

```python
classify_indirect_control_flow(translation_units: TranslationUnitSet, *,
                               evidence: Iterable[IndirectControlFlowEvidence] = ()) -> IndirectControlFlowSet
classify_indirect_control_flow_from(units: Iterable[TranslationUnit], *, source: ProgramSource,
                                    unowned_control_flow: Iterable[UnresolvedSite] = (),
                                    evidence: Iterable[IndirectControlFlowEvidence] = ()) -> IndirectControlFlowSet
```

`IndirectControlFlowSet` exposes `units`, `source`, `unowned_control_flow`,
`classifications()`, `unit_for(function_id)`, `unit_by_id(unit_id)`,
`classification_for(function_id, block_id, address, kind)`, `status_counts()`,
`to_document()`, `serialize()`, `fingerprint()`, `from_document()` and `deserialize()`.

## Classification categories

`IndirectControlFlowStatus`:

1. `RESOLVED` â€” evidence proves an exact target or a finite exact target set.
2. `BOUNDED_CANDIDATES` â€” evidence establishes a bounded candidate set but does not prove
   which target is selected. **Never treated as resolved.**
3. `EXTERNAL_OR_RUNTIME_MEDIATED` â€” proven to transfer through an external/runtime
   mechanism; no internal target is invented.
4. `RETURN_LIKE` â€” proven return-like indirect transfer (indirect jumps only).
5. `UNRESOLVED_INDIRECT_CALL` â€” indirect call remains unresolved.
6. `UNRESOLVED_INDIRECT_JUMP` â€” indirect jump remains unresolved.
7. `UNSUPPORTED_OR_MALFORMED` â€” structurally inconsistent/unsupported; fail closed.

`IndirectControlFlowKind` mirrors the neutral P2-01/P2-02 flow: `INDIRECT_CALL`,
`INDIRECT_JUMP`. The classifier integrates with `InstructionFlow` rather than duplicating
semantics: kind is derived from the instruction's `INDIRECT_CALL` / `INDIRECT_JUMP` flow.

## Proof bases and resolution rules

Every classification carries an explicit `IndirectControlFlowBasis`:

| Basis | Status | Rule |
| --- | --- | --- |
| `EXACT_CONSTANT_TARGET` | `RESOLVED` | exactly one proven target |
| `EXACT_TARGET_SET` | `RESOLVED` | at least two proven exact targets |
| `ADAPTER_EVIDENCE` | `RESOLVED` / `BOUNDED_CANDIDATES` | explicit architecture-adapter proof |
| `BOUNDED_CANDIDATE_EVIDENCE` | `BOUNDED_CANDIDATES` | at least one candidate target, none proven |
| `EXTERNAL_RUNTIME_EVIDENCE` | `EXTERNAL_OR_RUNTIME_MEDIATED` | named external mechanism, no internal target |
| `STRUCTURAL_RETURN_EVIDENCE` | `RETURN_LIKE` | proven return idiom, indirect jump only |
| `NONE` | unresolved / unsupported | no positive proof |

Implemented proof rules:

- A positive classification exists only when a matching `IndirectControlFlowEvidence`
  record is supplied by a trusted adapter or fixture. The classifier **never generates**
  evidence.
- `RESOLVED` requires `EvidenceClass.PROVEN` evidence; a `CANDIDATE` exact-target claim is
  rejected (`RESOLVED requires PROVEN evidence`) rather than promoted.
- `RESOLVED` requires at least one target; `EXACT_CONSTANT_TARGET` requires exactly one;
  `EXACT_TARGET_SET` requires at least two.
- `BOUNDED_CANDIDATES` requires at least one candidate and stays `BOUNDED_CANDIDATES`.
- `EXTERNAL_OR_RUNTIME_MEDIATED` requires a non-empty mechanism label and forbids internal
  targets; `RETURN_LIKE` forbids targets and applies only to indirect jumps.
- Targets matching discovered `TranslationUnit` entry addresses are additionally recorded
  in `target_functions`; targets that do not match an entry keep their exact address and
  fabricate no function.
- No address-shaped integer, nearby code, opcode, reason string or adapter metadata is ever
  used to synthesise a target.

## Evidence record

`IndirectControlFlowEvidence` identifies the exact structural site
(`function_id`, `block_id`, `address`, `kind`) and declares a positive `status` with a
`basis`, optional `targets`, optional `external_mechanism`, optional `detail`, a `source`
provenance label and an `EvidenceClass`. Records are canonicalized
(targets sorted/unique, validated non-negative). Duplicate keys, conflicting duplicate
claims, unknown sites, wrong-kind sites and malformed/contradictory claims fail closed.

## Classification record and provenance

`IndirectControlFlowClassification` preserves:

- source function identity (`unit_id`, `function_id`, `entry_address`);
- source block identity (`block_id`);
- source instruction/site identity (`address`, `op`, `kind`);
- the original P2-01/P2-02 `UnresolvedSite` (`unresolved_site`) including its `reason` and
  `EvidenceClass`;
- the classification `status`, `basis`, `targets`, `target_functions`,
  `external_mechanism`, `detail`, `evidence` and machine-readable `provenance`.

`provenance` names the structural layers that produced the site plus the evidence source,
for example `"P2-02:InstructionFlow.INDIRECT_CALL"`, `"P2-04:CallGraphEdge.UNRESOLVED_INDIRECT"`,
`"P2-05:TranslationUnit.unresolved_call_sites"`, `"evidence:fixture"`.

## Integration with TranslationUnitSet

`classify_indirect_control_flow` reads the P2-05 `TranslationUnitSet` without mutating it
(the test asserts the set fingerprint is unchanged). Sites are enumerated from the unit
block instructions and cross-checked against:

- the unit's `unresolved_call_sites` / `unresolved_jump_sites` (`(block, address, op)`);
- the P2-04 `UNRESOLVED_INDIRECT` call edges for each caller.

Any disagreement fails closed. `target_functions` are derived from unit entry addresses.
Unowned control flow carried by the P2-05 set is preserved verbatim as
`IndirectControlFlowSet.unowned_control_flow` and is not classified, because its call/jump
kind cannot be established without inventing information.

## Determinism

- Units are ordered by `(entry_address, function_id)`; within a unit classifications are
  ordered by `(address, kind, block_id)`; targets, target functions, provenance and
  residual sites are canonicalized/sorted.
- `to_document()` emits `indirect_control_flow_version = "1.0.0"`, source, units and
  residual unowned control flow; `serialize()` is canonical JSON; `fingerprint()` is its
  SHA-256. Two consecutive gate runs produced byte-identical stdout
  (`sha256 866d290a59228e5bd01f5bc026d2a2b1ca5558e28e9165b2dea42e00464d72a2`), and
  serialize/deserialize round-trips are byte-identical. See `determinism.txt`.

## Tests / coverage

```text
python tools/test_indirect_control_flow_v1.py
OPENRECOMP_INDIRECT_CONTROL_FLOW_V1=PASS tests=134
```

Coverage: deterministic classification and repeated construction; canonical ordering
across multiple units and input-order independence; stable serialization and round-trip
identity; exact resolved target and exact finite proven target set (including targets that
do not match a function entry); bounded candidates that never become resolved (including
with CANDIDATE evidence); candidate canonicalization; unresolved indirect call and jump
preservation; external/runtime-mediated preservation; return-like classification when
positively proven and non-classification when proof is absent; source function/block/
instruction provenance; proof basis; unresolved-reason preservation; no invented target
from metadata addresses or nearby code; no candidate promotion; duplicate/conflicting
evidence rejection; malformed/unknown enum/status/basis rejection; missing provenance
rejection; contradictory target/status rejection; address boundaries; 64-bit and >64-bit
round-trip; multiple and empty translation units; preservation of P2-05 structure; a
bounded NES6502 indirect-jump fixture; and no IR lowering / host emission.

## Fail-closed behavior

`IndirectControlFlowError` (never heuristic repair) for:

1. malformed/contradictory evidence claims (missing targets, too many/few targets for the
   basis, wrong basis for the status, mechanism missing/forbidden, targets on a non-resolved
   status, NONE basis on a proof claim, `RESOLVED` with `CANDIDATE` evidence, negative or
   duplicate targets);
2. evidence for an unknown site or of the wrong kind;
3. duplicate or conflicting evidence for one site;
4. non-`TranslationUnitSet` / non-`TranslationUnit` / empty-unit / non-evidence input;
5. structural inconsistency between instructions, P2-05 unresolved sites and P2-04
   unresolved call edges;
6. malformed classification documents: missing provenance, missing unresolved-site
   provenance, unknown status/basis/kind/evidence value, contradictory targets/status, and
   an unsupported `indirect_control_flow_version`;
7. malformed JSON / non-object documents;
8. invalid unit/set structure (duplicate ids, duplicate entries, a classification that
   does not belong to its unit, residual unowned sites whose block is owned);
9. unknown unit/function/site lookups.

## Regression gates

```text
OPENRECOMP_INDIRECT_CONTROL_FLOW_V1=PASS tests=134
OPENRECOMP_TRANSLATION_UNITS_V1=PASS tests=104
OPENRECOMP_CALL_GRAPH_V1=PASS tests=61
OPENRECOMP_FUNCTION_DISCOVERY_V1=PASS tests=67
OPENRECOMP_CFG_V1=PASS tests=82
OPENRECOMP_PROGRAM_MODEL_V1=PASS tests=49
OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
PASS source-integrity  verified 116 manifest entries
```

The two toolchain-gated Phase-1 gates (`e07-hardened-end-to-end`,
`external-repro-v1`) remain unexecutable on this host (missing `gcc`, `posix`) and are
never counted as pass.

## Architecture-neutrality assessment

`openrecomp/indirect_control_flow.py` imports only neutral P2 types
(`openrecomp.call_graph`, `openrecomp.program_model`, `openrecomp.translation_units`). It
contains no opcode table, calling convention, link register, delay slot, stack frame,
fixed/variable width, endianness, address-width or console assumption. Addresses are
arbitrary-precision integers. The same code path handles synthetic 32-bit, 64-bit and
>64-bit input and a bounded 16-bit NES6502-derived indirect jump.

## Known limitations

- Classification consumes explicit evidence; it does not recover targets by analysis.
  This is intentional (unknown remains unknown).
- Indirect jump tables, constant propagation, symbolic execution, pointer scanning and ABI
  recovery are out of scope and were not attempted.
- Unowned control flow is preserved as residual evidence but cannot be classified because
  its call/jump kind is not structurally attributable.
- `schema/*.json` and `openrecomp/*.py` remain outside `SOURCE_SHA256SUMS.txt`
  (pre-existing `update_sums.py` `schemas/` glob gap); the new files are covered by the
  hashes in `determinism.txt`.
- Toolchain-gated Phase-1 gates remain skipped on this host.

## Explicit non-claims

P2-06 does **not** claim automatic indirect-target recovery, jump-table recovery, constant
propagation, symbolic execution, ABI/calling-convention recovery, IR lowering, host
emission, AOT integration, whole-game recompilation, console compatibility, generic runtime
support or RT64 integration. The NES6502 validation is a bounded structural test.

## Boundary rule

No P2-06 git commit was created. The coherent P2-06 changes are left in the working tree
for independent review and boundary commit. P2-07 (Host emitter V1) was **not** started.

## Final verdict

`PASS` â€” every supported indirect-control-flow site now receives a deterministic explicit
classification; unknown/unproven targets remain unresolved; bounded candidates are never
promoted; every resolved classification has machine-readable provenance; serialization and
round-trips are byte-identical; P2-05 structure is preserved; no IR is lowered and no host
code is emitted.

OPENRECOMP_P2_06=PASS
OPENRECOMP_INDIRECT_CONTROL_FLOW_V1=PASS tests=134
