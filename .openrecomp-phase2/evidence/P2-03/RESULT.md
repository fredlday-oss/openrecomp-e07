# P2-03 — Deterministic architecture-neutral function discovery V1

VERDICT: `PASS`

STAGE MARKER: `OPENRECOMP_P2_03=PASS`
DISCOVERY GATE MARKER: `OPENRECOMP_FUNCTION_DISCOVERY_V1=PASS tests=67`

## Baseline

| Item | Value |
| --- | --- |
| Stage | `OPENRECOMP_P2_03_FUNCTION_DISCOVERY_V1` |
| Branch | `phase2/opencode-v1` |
| Starting commit | `65386e45f9af1d581d0e14f8cca3940a6a82d75c` (P2-02 boundary; `HEAD` at start) |
| P2-00 boundary | `1b40269cc80cd19d49d8870f8e65aa1eced69885` |
| P2-01 boundary | `a0c483029727168b1371aa9683e82900f9e14638` |
| Phase-1 freeze | tag `openrecomp-phase1-pass` -> `46c2f971e1a42cf49bd936bad94697b81bf31002` (verified unchanged) |
| P2-02 gate | `OPENRECOMP_CFG_V1=PASS tests=82` (re-verified) |
| P2-01 gate | `OPENRECOMP_PROGRAM_MODEL_V1=PASS tests=49` (re-verified) |

Pre-flight: branch correct; `HEAD` equals the P2-02 boundary; the Phase-1 tag still
resolves to the frozen commit; starting `git status` showed only the excluded untracked
paths `.openrecomp-phase2/backups/`, `artifacts/mips32_translation_v1/`,
`artifacts/mips32_translation_evidence_closure_v1/` (left untouched).

## Files added

| File | Role |
| --- | --- |
| `openrecomp/functions.py` | Neutral function discovery: `discover_functions`, `FunctionDiscoveryResult`, `FunctionDiscoveryError`, `FunctionEntry`, `FunctionEntrySource`, `EntryBasis`, `SuppressedEntry`, `SharedBlock`, `ExternalDirectCallTarget`. |
| `tools/test_functions_v1.py` | Deterministic 67-check discovery gate with optional `--json` record. |
| `.openrecomp-phase2/evidence/P2-03/*` | This evidence bundle. |

## Files modified

| File | Change |
| --- | --- |
| `openrecomp/program_model.py` | Backwards-compatible `FunctionUnit` additions: optional `entry_sources` tuple (entry provenance), and a `canonical_blocks()` serialization order (entry block first, remaining blocks sorted by `(entry_address, id)`). `to_document()` now uses `canonical_blocks()` and emits `entry_sources` only when non-empty; `from_document()` reads it. This corrects a P2-01 limitation that prevented round-tripping a function whose entry address is not its lowest owned block (backward-flow/loop bodies). |
| `schema/openrecomp-program-v1.schema.json` | Added `entry_sources` as an **optional** function property (`array` of non-empty unique strings). Not required; existing documents without it stay valid. |
| `SOURCE_SHA256SUMS.txt` | Registered `tools/test_functions_v1.py` via `update_sums.py` (112 -> 113 entries). No existing hash changed. |
| `.openrecomp-phase2/STATE.md`, `HANDOFF.md` | Stage transition (P2-03 PASS -> P2-04). |

Frozen IR V1 (`ir_version = 1.0.0`), Module Image V1 (`1.0.0`), Core API, the AOT/native
ABI, the P2-02 CFG builder and all Phase-1 adapters/frontends are untouched. Existing
P2-01/P2-02 serializations where the entry block is the lowest-address block are
byte-compatible (entry-first order equals address order there; `entry_sources` is
omitted when empty). No P2-01/P2-02 test was weakened.

## Public API

```python
discover_functions(cfg, *, program_entries=(), function_entries=(),
                   include_direct_call_targets=True) -> FunctionDiscoveryResult
```

- `program_entries`: `int | EntryPoint`. An int defaults to `PROVEN` evidence
  (authoritative program/executable entry); an `EntryPoint` may override.
- `function_entries`: `int | FunctionEntry`. An int defaults to
  `EXPLICIT_CANDIDATE`/`CANDIDATE`; a `FunctionEntry` carries its own source/evidence.
- `include_direct_call_targets`: derive entries from `ControlFlowGraph.direct_call_sites`.

`FunctionDiscoveryResult` exposes `functions` (sorted by `(entry_address, id)`),
`provenance` / `basis(function_id)`, `suppressed_entries`, `shared_blocks`,
`external_direct_call_targets`, `unowned_blocks`, `entry_function_id`,
`to_program_model()`, `to_document()`, `serialize()`, `fingerprint()`. Construction
builds and validates the P2-01 `ProgramModel`, so an invalid partition fails closed.

## Function-entry sources

| Source | Basis | Evidence |
| --- | --- | --- |
| `PROGRAM_ENTRY` | supplied program/executable entry | caller (int default `PROVEN`) |
| `DIRECT_CALL` | a `ControlFlowGraph.direct_call_sites` target inside the region | call-site evidence |
| `EXPLICIT_PROVEN` | caller-supplied proven function entry | `PROVEN` |
| `EXPLICIT_CANDIDATE` | caller-supplied candidate function entry | `CANDIDATE` |

Multiple independent bases for one address are preserved (all recorded in `EntryBasis`
and in `FunctionUnit.entry_sources`, sorted). The entry is considered `PROVEN` if at
least one independent source is `PROVEN`; the final `FunctionUnit.evidence` remains
conservative (see evidence propagation).

## Discovery / traversal algorithm

1. Validate and group entry bases by address; every caller-supplied entry must resolve
   to a CFG block entry (fail closed otherwise). Direct-call targets outside the CFG are
   recorded as external targets, never turned into functions. A direct-call target that
   is an instruction start but not a block boundary fails closed (inconsistent
   call-derived entry).
2. For each entry, compute its raw reachable block set by BFS over **resolved**
   successors, stopping at the entry block of any other entry of equal-or-stronger
   evidence rank. This keeps a caller out of a known callee's entry and bounds traversal.
3. Process entries in deterministic priority order (`PROVEN` before `CANDIDATE`, then
   lower address). Claim each entry's still-unclaimed reachable blocks. If an entry's
   own block is already owned it is either suppressed (weaker candidate) or fails
   closed (contradictory PROVEN ownership).
4. Build one P2-01 `FunctionUnit` per surviving entry, with the entry block first and
   the rest sorted by `(entry_address, id)`.

Loops terminate through a visited set; recursion and mutual recursion produce separate
entries with no infinite traversal.

## Call-boundary rules

- A direct call produces only the caller's `CALL_RETURN` continuation edge in the CFG;
  the callee's blocks are never reached by that edge.
- A direct-call target inside the region becomes a **separate** function entry; the
  caller never owns callee blocks.
- A resolved non-call edge that reaches another entry block (tail call / fallthrough
  between functions) stops traversal at that boundary and is left as a cross-function
  resolved edge; the target stays owned by its own function.
- The callee never absorbs the caller continuation.
- `direct_callees` are populated provisionally (direct calls only) and `direct_call_sites`
  provide the source-site inventory for P2-04. This is **not** the final validated
  whole-program call graph.

## Ownership rules

- Claim priority: `(evidence_rank, address)` with `PROVEN` rank 0, `CANDIDATE` rank 1.
- A `CANDIDATE` entry whose entry block is already owned by a `PROVEN` function is
  **suppressed** with an explicit reason and owner (never promoted).
- Two `PROVEN` entries that would claim the same entry block fail closed (defensive
  guard; the equal-or-stronger stop rule normally prevents this by keeping both
  functions' entries disjoint).
- Deterministic partition means every CFG block is owned by at most one `FunctionUnit`,
  satisfying the P2-01 unique-block-ownership model.

## Shared-block policy

A non-entry block reachable from multiple function entries is assigned to the
highest-priority owner. The fact is recorded explicitly in `shared_blocks`
(`block`, `owner`, `also_reachable_from`). Cross-function resolved edges to that block
remain representable (P2-01 allows cross-function resolved successors), so structure is
not lost; a block is never given to two `FunctionUnit`s. Blocks not reachable from any
entry are listed in `unowned_blocks` (disconnected regions are not invented).

## Evidence propagation rules

- Entry evidence = `PROVEN` if any independent source is `PROVEN`, else `CANDIDATE`.
- Function evidence = `combine_evidence(entry_evidence, all owned block evidence, all
  internal (within-body) edge evidence)`: `PROVEN` only if every input is `PROVEN`.
- A `CANDIDATE` entry or a `CANDIDATE` block always yields a `CANDIDATE` function;
  traversal success never raises confidence.
- Classifications and `entry_sources` survive serialization/deserialization.

## Unresolved-indirect policy

Indirect calls and jumps remain unresolved: traversal does not follow them, no target
set is invented, and no `FunctionUnit` is created for an indirect target unless an
independent entry source (program/explicit/direct-call) names it. Unresolved call sites
are attached to the owning function's `unresolved_call_sites`.

## Architecture-neutrality analysis

`openrecomp/functions.py` imports only P2-01/P2-02 neutral types and contains no ISA
knowledge or heuristics: no prologue/epilogue, alignment, symbol-name, stack-frame,
calling-convention, link-register or fixed-width assumptions. Entries come only from
explicit evidence; traversal uses neutral `resolved` successors; addresses are
arbitrary-precision integers; instruction extent is not consulted for discovery beyond
the CFG. The same code path handles a 64-bit synthetic guest, a 32-bit synthetic guest,
and a real 16-bit NES6502 stream.

## Fail-closed rules

Rejected/classified without heuristic repair (`FunctionDiscoveryError`, or the P2-01
`ProgramModelError` surfaced by validation):

1. entry absent from the CFG (program/explicit) — fail closed;
2. entry into an instruction interior or a non-block instruction start — fail closed;
3. invalid/contradictory `FunctionEntry` source/evidence (e.g. `EXPLICIT_PROVEN` with
   `CANDIDATE`) — fail closed;
4. direct-call target inside the region but not a block boundary — fail closed;
5. no entries at all — fail closed;
6. caller traversal entering a known callee entry — stopped at the boundary and left as
   an explicit cross-function edge;
7. candidate entry inside a proven function — suppressed with an explicit reason;
8. contradictory PROVEN ownership of one entry block — fail closed (defensive);
9. shared non-entry block — deterministic single owner + explicit `shared_blocks` record;
10. disconnected region without an entry — recorded as `unowned_blocks`, not invented;
11. malformed function membership (overlapping blocks) — rejected by the P2-01
    `ProgramModel` validator invoked from the result constructor;
12. unresolved indirect targets — never promoted to functions;
13. cycles/recursion/mutual recursion — terminate deterministically via visited sets.

## Tests / count

```text
python tools/test_functions_v1.py
OPENRECOMP_FUNCTION_DISCOVERY_V1=PASS tests=67
```

Coverage: one/multiple explicit entries; program entry; direct-call discovery; caller
does not absorb callee; callee does not absorb caller continuation; multiple calls to
one callee; recursion; mutual recursion; return/trap termination; internal branch;
internal loop; multi-block functions; disconnected regions; explicit CANDIDATE/PROVEN
entries; PROVEN/CANDIDATE direct-call targets; unresolved indirect call/jump
non-discovery; addresses above `0xFFFFFFFF`; real NES6502-derived CFG; deterministic
function ordering, block membership, serialization and fingerprint; candidate-inside-
proven suppression; proven-nested handling; shared-tail policy; external direct-call
inventory; entry block above a lower reachable block (serialize/deserialize/serialize
stability); `entry_sources` schema round-trip and omission when empty; and all
fail-closed rejections above.

## Deterministic repeated-run comparison

```text
run 1 == run 2 stdout (byte-identical)
stdout sha256 = 05218d8d1db991e2ff93679340490d59dcea24add7c3c8d2faee0bf26cbe39a8
```

Sample fingerprints:

```text
call         discovery=408f90be68e76fb31192cd44f5a279ce5f729edd6d0c394f7fef88e9ce84beb3
             program  =690a692fe1b0cfcbd8049ce722e2ddf670bba176bfb9481d1be00dc91736bc7a
nes6502      discovery=8e75f0a3e2f6e619c6e6ee15c0ee1e15e85feed15e8de572b7283bb4259be7bb
wide         discovery=cfbf7bec9ebaffcc109c14f323fa9628e6cee2854c8e4b7744b011e982f0195d
shared_tail  discovery=f69f8e32df5d0ddc8c188b4111a05d250be3fd2734477f8373eb88a6c50ca3f1
```

(These values are also recorded in `function_tests.json`.)

## P2-02 regression result

```text
python tools/test_cfg_v1.py
OPENRECOMP_CFG_V1=PASS tests=82
```

## P2-01 regression result

```text
python tools/test_program_model_v1.py
OPENRECOMP_PROGRAM_MODEL_V1=PASS tests=49
```

The P2-01 `FunctionUnit` changes are additive/backwards-compatible (optional field +
deterministic canonical order); all 49 P2-01 checks pass.

## Phase-1 regression result

```text
python tools/phase1_host_gates_v1.py --json .openrecomp-phase2/evidence/P2-03/host_gates.json
OPENRECOMP_PHASE1_HOST_GATES_PASS=44 FAIL=0 SKIPPED=2
OPENRECOMP_PHASE1_HOST_GATES_V1=PASS
```

Same 44 PASS / 0 FAIL / 2 toolchain skips (`e07-hardened-end-to-end`,
`external-repro-v1`) as prior baselines.

## Source-integrity result

```text
python tools/phase1_host_gates_v1.py --only source-integrity
PASS source-integrity  verified 113 manifest entries
```

`SOURCE_SHA256SUMS.txt` gained exactly one entry (`tools/test_functions_v1.py`) via
`update_sums.py`; no existing hash changed.

## Deterministic artifacts

| Artifact | SHA-256 |
| --- | --- |
| `function_tests.json` | `1cc8758a5ec978244f72f861bac214dad1f5e757b73f385887016e3fdbc19c47` |
| `function_tests.txt` (UTF-8) | `05218d8d1db991e2ff93679340490d59dcea24add7c3c8d2faee0bf26cbe39a8` |
| `host_gates.json` | `6c276325f3281865c7037c94b3ab6f90ac0d54d37862a7bfa2b3bb46986041db` |
| `host_gates.txt` (UTF-8) | `5d817fbb30338a2af295257bafe56136775a7e1d3702a5d8ddd0856d3e55529d` |
| `sample_functions.program.json` (P2-01 view) | `690a692fe1b0cfcbd8049ce722e2ddf670bba176bfb9481d1be00dc91736bc7a` |
| `sample_functions.discovery.json` | `408f90be68e76fb31192cd44f5a279ce5f729edd6d0c394f7fef88e9ce84beb3` |
| `openrecomp/functions.py` | `c07a0c53ec13cecfb036cb4cf46a35ec7087c14f4e675d033730f02193a5055a` |
| `openrecomp/program_model.py` | `a4ace1ae01cc7f86f6c863496a11be903f9e944ac27f91ea85d4846f981f172f` |
| `schema/openrecomp-program-v1.schema.json` | `c1ed71199b541701cf03fd05f7589e0dd8722d276f049a7cb5b6709c4e813afe` |
| `tools/test_functions_v1.py` | `ed7cbe654768280d3e9a7c1120e94308cd90e2323542e78b0c29563e4d5804cf` |

Text evidence is UTF-8 without BOM.

## Schema

One optional property added (`entry_sources`); no required-field change. The discovered
`ProgramModel` view validates against the schema and `tools/validate_program_model_v1.py`
(exercised by the tests). Existing P2-01/P2-02 documents remain valid.

## Limitations

- Function discovery is evidence-entry driven; it does not invent entries from byte
  patterns, prologues, alignment, symbols or ABI heuristics.
- `direct_callees` are provisional structural facts; the final validated whole-program
  call graph is deferred to P2-04.
- Shared non-entry blocks have a single deterministic owner; genuine concurrent
  ownership is not represented (P2-01 ownership is unique by design).
- External direct-call targets are inventoried, not discovered.
- `schema/*.json` and `openrecomp/*.py` remain outside `SOURCE_SHA256SUMS.txt`
  (pre-existing `update_sums.py` `schemas/` glob gap); covered by tests and the hashes
  above.
- Toolchain-gated Phase-1 gates remain skipped on this host.

## Explicit non-claims

P2-03 does **not** claim complete or heuristic function recovery, indirect-call
resolution, the final whole-program call graph, jump-table recovery, calling-convention
or ABI recovery, translation-unit construction, IR lowering, AOT integration, whole-game
recompilation, console compatibility, generic runtime support, or RT64 integration. The
NES6502 validation is a bounded structural test, not full NES function discovery.

## Recommended P2-04 frontier

Whole-program direct-call-graph construction and validation over the discovered
functions: consolidate `direct_call_sites` into a validated inter-function direct call
graph, keep unresolved indirect calls separate (per `AGENTS.md`), and validate graph
consistency (callee declaration, recursion, cross-function edges) using neutral
evidence rules. Do not implement translation units (P2-06) or the host emitter (P2-07).

## Final verdict

`PASS` — deterministic, architecture-neutral function discovery exists on the P2-02 CFG
and P2-01 model, with 67 deterministic checks, the P2-02 (82) and P2-01 (49) suites
green, 44 Phase-1 gates green, and source integrity verified.
