# P2-04 — Deterministic architecture-neutral call-graph recovery V1

VERDICT: `PASS`

STAGE MARKER: `OPENRECOMP_P2_04=PASS`
CALL-GRAPH GATE MARKER: `OPENRECOMP_CALL_GRAPH_V1=PASS tests=61`

## Baseline

| Item | Value |
| --- | --- |
| Stage | `OPENRECOMP_P2_04_CALL_GRAPH_RECOVERY_V1` |
| Branch | `phase2/opencode-v1` |
| Starting commit | `aa263bbedbd74a3dd0311fbf149a901cd50d7e44` (P2-03 boundary; `HEAD` at start) |
| P2-00 boundary | `1b40269cc80cd19d49d8870f8e65aa1eced69885` |
| P2-01 boundary | `a0c483029727168b1371aa9683e82900f9e14638` |
| P2-02 boundary | `65386e45f9af1d581d0e14f8cca3940a6a82d75c` |
| Phase-1 freeze | tag `openrecomp-phase1-pass` -> `46c2f971e1a42cf49bd936bad94697b81bf31002` (verified unchanged) |
| Prior gates | `OPENRECOMP_FUNCTION_DISCOVERY_V1=PASS tests=67`, `OPENRECOMP_CFG_V1=PASS tests=82`, `OPENRECOMP_PROGRAM_MODEL_V1=PASS tests=49` |

Pre-flight: branch correct; `HEAD` equals the P2-03 boundary; the Phase-1 tag still
resolves to the frozen commit; starting `git status` showed only the excluded untracked
paths `.openrecomp-phase2/backups/`, `artifacts/mips32_translation_v1/`,
`artifacts/mips32_translation_evidence_closure_v1/` (left untouched).

## Files added

| File | Role |
| --- | --- |
| `openrecomp/call_graph.py` | Neutral call-graph layer: `build_call_graph`, `build_call_graph_from`, `CallGraph`, `CallGraphNode`, `CallGraphEdge`, `CallEdgeKind`, `CallGraphError`. |
| `tools/test_call_graph_v1.py` | Deterministic 61-check call-graph gate with optional `--json` record. |
| `.openrecomp-phase2/evidence/P2-04/*` | This evidence bundle. |

## Files modified

| File | Change |
| --- | --- |
| `SOURCE_SHA256SUMS.txt` | Registered `tools/test_call_graph_v1.py` via `update_sums.py` (113 -> 114 entries). No existing hash changed. |
| `.openrecomp-phase2/STATE.md`, `HANDOFF.md` | Stage transition (P2-04 PASS -> P2-05). |

No P2-01/P2-02/P2-03 source was modified. Frozen IR V1 (`ir_version = 1.0.0`), Module
Image V1 (`1.0.0`), Core API, the AOT/native ABI, the CFG builder and function
discovery are untouched. No prior test was weakened.

## Call-graph public API

```python
build_call_graph(discovery: FunctionDiscoveryResult) -> CallGraph
build_call_graph_from(cfg: ControlFlowGraph, functions, *,
                      entry_function_id, external_direct_call_targets=()) -> CallGraph
```

`CallGraph` exposes `nodes`, `edges`, `node(id)`, `edges_from(id)`, `edges_to(id)`,
`internal_edges()`, `external_edges()`, `unresolved_edges()`, `callees(id)`,
`recursive_functions()`, `strongly_connected_components()`,
`mutual_recursion_components()`, `to_document()`, `serialize()`, `fingerprint()`,
`from_document()` and `deserialize()`. Construction validates immediately and fails
closed.

## Graph-node representation

Each discovered P2-03 `FunctionUnit` maps to exactly one `CallGraphNode`
(`function_id`, `entry_address`, `evidence`). Node identity reuses the stable
`FunctionUnit.id` (`fn_<entry hex>`); no second function namespace is introduced. Nodes
are emitted in `(entry_address, function_id)` order. A node's evidence must equal its
`FunctionUnit.evidence` when the units are supplied to the validator.

## INTERNAL_DIRECT policy

A direct `CallSite` whose `target_address` exactly equals a discovered `FunctionUnit`
entry address produces an `INTERNAL_DIRECT` edge `caller -> callee`, identified by the
exact calling site `(block, address, op)`. Edge evidence is
`combine_evidence(site.evidence, callee_node.evidence)` (conservative: `PROVEN` only when
both are). The caller's derived internal-callee set is reconciled with
`FunctionUnit.direct_callees` during validation.

## EXTERNAL_DIRECT policy

A direct `CallSite` whose target is not a discovered function entry (and not a CFG block
boundary) produces an `EXTERNAL_DIRECT` edge carrying `target_address` and no callee. No
node is invented. The set of external targets recovered from call sites must equal the
P2-03 `FunctionDiscoveryResult.external_direct_call_targets` inventory, or construction
fails closed.

## UNRESOLVED_INDIRECT policy

Every P2-02 `ControlFlowGraph.unresolved_call_sites` entry produces one
`UNRESOLVED_INDIRECT` edge for its owning function, with no callee and no
`target_address`. Indirect targets are never guessed. `unresolved_jump_sites` are
deliberately **excluded** — the call graph records calls only; indirect jumps do not
create call edges or nodes.

## Exact caller ownership

`build_call_graph_from` builds `block_owner: block_id -> function_id` from the supplied
`FunctionUnit.blocks` and requires every call site's block to be owned by exactly one
function. A call site whose block is unowned fails closed; a block owned by more than one
function fails closed. This is how P2-03 ownership (not re-discovery) assigns callers.

## Exact callee entry matching

Callees are resolved only by exact equality between a direct `CallSite.target_address`
and a discovered `FunctionUnit.entry_address`. No range, alignment, heuristic or
near-match resolution is performed.

## Direct target into function-interior policy

Three cases are distinguished for a direct call target:

1. exact `FunctionUnit` entry -> `INTERNAL_DIRECT`;
2. a CFG block boundary that is **not** a discovered function entry (a call into a
   function interior or a suppressed candidate entry) -> fail closed
   (`... is a CFG block boundary but not a discovered function entry`);
3. outside the supplied CFG region -> `EXTERNAL_DIRECT`.

Targets that fall strictly inside an instruction extent are already rejected by P2-03
function discovery, so they cannot reach this layer.

## FunctionUnit.direct_callees reconciliation

When `function_units` are supplied (always, via `build_call_graph_from`), the validator
compares each node's derived internal-callee set against `FunctionUnit.direct_callees`
(provisional P2-03 facts). Any disagreement fails closed. This binds the P2-04 call graph
to the P2-01/P2-03 model rather than silently diverging.

## Per-callsite preservation

Edges are keyed by the exact calling site (`call_site_block`, `call_site_address`,
`call_site_op`), so multiple calls between the same pair remain distinct edges, and
duplicate edge identities are rejected. Each edge carries the call-site evidence
combined with callee evidence for internal edges.

## Recursion / self-recursion / mutual recursion / cycle handling

- Self-recursion: an `INTERNAL_DIRECT` edge with `caller == callee`; reported by
  `recursive_functions()`.
- Mutual recursion: strongly connected components of size >= 2 over internal edges,
  reported by `mutual_recursion_components()`.
- `strongly_connected_components()` uses an iterative Kosaraju traversal over
  deterministically sorted adjacency, so cycles terminate and are ordered
  deterministically.

## Root-function definition

`CallGraph.entry_function` is the P2-03 `FunctionDiscoveryResult.entry_function_id`: the
lowest-address `PROGRAM_ENTRY` function when a program entry exists, otherwise the
lowest-address discovered function. It must name a call-graph node (validated); there is
no separate root computation in P2-04.

## Evidence propagation rules

- Internal edge evidence = `combine_evidence(call-site evidence, callee node evidence)`.
- External and unresolved edge evidence = the P2-02 call-site evidence.
- Node evidence = the P2-03 `FunctionUnit.evidence`.
- `CANDIDATE` is never promoted by graph construction; classifications survive
  serialization/deserialization.

## Deterministic serialization / fingerprint

`to_document()` emits `call_graph_version = "1.0.0"`, `entry_function`, sorted `nodes`,
sorted `edges` (by `caller, call_site_address, kind, callee, target`), plus derived
`recursive_functions` and `mutual_recursion_components`. `serialize()` is canonical JSON;
`fingerprint()` is its SHA-256. Two runs produced byte-identical stdout.

```text
run 1 == run 2 stdout (byte-identical)
stdout sha256 = ee4602245dfad5301385b958826dca112c0b600d7e418a37954d39172ea9b374
```

Sample fingerprints:

```text
internal  7a46071aab7d18ffa46a773c7774e12ecb02340decefa8f2c0fe8e0ce0988b30
mixed     8fe4925fbe988ad2c2bf8cda1a1f6ce8234f5740f21a95c1ac5dd7f0b40a2446
mutual    586bd1f6ccb06f2f03db7231c31215282699737179568e75f78ab1858e949692
nes6502   ab4c2dc12adc549eac85f55d58ede8fc3ed2721ce8e802971dcdfa9f4bc4b777
```

## Tests / count

```text
python tools/test_call_graph_v1.py
OPENRECOMP_CALL_GRAPH_V1=PASS tests=61
```

Coverage: one node per function; internal direct edges (callee/evidence/edges_to/callees);
external direct edges (target, no node invented); unresolved indirect edges (no
target/callee, no callee node); indirect-jump exclusion; self-recursion;
mutual-recursion components; multiple call sites between the same pair; PROVEN/CANDIDATE
edge and node evidence; deterministic node/edge order, serialization, fingerprint and
round-trip; addresses above `0xFFFFFFFF`; bounded NES6502-derived call graph; cross-check
against the P2-01 `ProgramModel.direct_call_graph()`; and all fail-closed rejections
below.

## Fail-closed behavior

`CallGraphError` (never heuristic repair) for:

1. a call site whose block is not owned by any discovered function;
2. a block owned by more than one function;
3. a direct call target that is a CFG block boundary but not a discovered function entry
   (function interior / suppressed candidate);
4. external direct-call inventory disagreeing with recovered external edges;
5. duplicate node identity or duplicate node entry address; empty node set;
6. an edge caller or internal callee that is not a node;
7. an external edge target that matches a node entry;
8. an unresolved edge carrying a callee/target, or an internal edge lacking a callee;
9. a duplicate edge identity;
10. an `entry_function` that is not a node;
11. `function_units` keys not matching node ids, entry/evidence disagreement, or
    `FunctionUnit.direct_callees` disagreeing with recovered internal callees;
12. unknown node lookups (`edges_from`/`edges_to`).

## Deterministic artifacts

| Artifact | SHA-256 |
| --- | --- |
| `call_graph_tests.json` | `e2714906076a04497a64cbf5f709446612e9aac98c41de8a885668f952b2e6ba` |
| `call_graph_tests.txt` (UTF-8) | `ee4602245dfad5301385b958826dca112c0b600d7e418a37954d39172ea9b374` |
| `host_gates.json` | `9a9d8491acfc700e0451730f9cd8752d279e6f8a24ace6440992456fb82ff06a` |
| `host_gates.txt` (UTF-8) | `dc85ab694bf5751fbda6afb00bcd6fd34e51cbc071bd22706fa64b9cf7affb22` |
| `sample_call_graph.json` (mixed canonical CallGraph) | `8fe4925fbe988ad2c2bf8cda1a1f6ce8234f5740f21a95c1ac5dd7f0b40a2446` |
| `openrecomp/call_graph.py` | `0dda2c55022842604e55d8d902d2523d83b116dbf61fb34bb949d94b7d1ea734` |
| `tools/test_call_graph_v1.py` | `8a4b136e620c13a5b5a6f885a3501c0cabb33ea8e669ba108aff04e6337139e0` |

Text evidence is UTF-8 without BOM. `sample_call_graph.json` is the canonical
serialization of the mixed fixture (nodes `fn_7000`, `fn_8000`; `INTERNAL_DIRECT`
`fn_7000 -> fn_8000`, `EXTERNAL_DIRECT` to `0x9000`, `UNRESOLVED_INDIRECT`).

## Architecture-neutrality assessment

`openrecomp/call_graph.py` imports only P2-01/P2-02/P2-03 neutral types. It contains no
ISA knowledge: no opcode tables, calling convention, link-register, stack-frame,
fixed/variable width, endianness, address-width or console assumption. Addresses are
arbitrary-precision integers. Callee resolution is exact entry-address equality;
ownership comes from neutral block membership. The same code path handles 32-bit
synthetic, 64-bit synthetic and 16-bit NES6502-derived graphs.

## Known limitations

- The call graph records **direct calls** only; indirect calls are unresolved and
  indirect jumps are excluded by design.
- `direct_callees` remain provisional structural facts; this stage validates them but
  does not perform semantic ABI/calling-convention recovery.
- Cross-function tail/fallthrough transfers remain CFG edges, not call edges.
- `schema/*.json` and `openrecomp/*.py` remain outside `SOURCE_SHA256SUMS.txt`
  (pre-existing `update_sums.py` `schemas/` glob gap); covered by tests and the hashes
  above.
- Toolchain-gated Phase-1 gates remain skipped on this host.

## Explicit non-claims

P2-04 does **not** claim indirect-call resolution, jump-table recovery, complete
whole-program call-graph recovery beyond the supplied region, calling-convention or ABI
recovery, translation-unit construction, IR lowering, AOT integration, whole-game
recompilation, console compatibility, generic runtime support or RT64 integration. The
NES6502 validation is a bounded structural test.

## Recommended P2-05 frontier

P2-05 (`Indirect-control-flow classification`) should classify indirect call/jump sites
against evidence without guessing targets: distinguish provably-resolvable forms from
genuinely unresolved ones, keep PROVEN/CANDIDATE provenance, and preserve the
`unresolved_call_sites` / `unresolved_jump_sites` separation already established here.

## Final verdict

`PASS` — a deterministic, architecture-neutral direct call graph now exists over the
P2-03 discovered functions, distinguishing internal/external/unresolved calls,
validating ownership and `direct_callees`, and reproducing 44 Phase-1 gates, the P2-03
(67), P2-02 (82) and P2-01 (49) suites, and source integrity (114 manifest entries).
