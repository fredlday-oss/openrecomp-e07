# OpenRecomp Phase 11 State

## Mission

Advance the exact audited private Hercules fixture (`SLUS_005.29`, legally
obtained, outside version control) beyond the Phase-10 milestone A and
establish the strongest reproducibly proven playability milestone possible,
through the existing OpenRecomp architecture. No second PS1 frontend, MIPS
decoder, CFG pipeline, host emitter or runtime is created; only
evidence-demonstrated gaps are extended.

## Baseline

- Phase-10 terminal commit `8961682aa36e14db979e8e8dbe88e04fa2b4c87a`, tree
  `4a58d9238d76a490560c588bb470fd9e6a58cafe`, branch
  `phase10/ps1-commercial-game-native-v1`.
- Phase-10 terminal verdict
  `OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=PASS` bounded to the
  exact private fixture and the demonstrated milestone A only.
- Inherited permanent Phase-10 non-claims (never promoted by Phase 11):
  `OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN`,
  `OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN`.
- Phase-11 work branch: `phase11/ps1-playability-v1`.

## Claim markers

- `OPENRECOMP_PHASE11_HERCULES_GPU_COMMAND_PROOF=PROVEN` (milestone C,
  private-fixture bounded: one genuine typed GP0 command write reached)
- `OPENRECOMP_PHASE11_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN` (promote only
  if milestone B is actually proven)
- `OPENRECOMP_PHASE11_HERCULES_FRAME_PROOF=NOT_PROVEN` (promote only if
  milestone D is actually proven)
- `OPENRECOMP_PHASE11_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN` (promote only if
  milestone G is actually proven)
- `OPENRECOMP_PHASE11_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)

## Terminal status

STATUS=COMPLETE
FINAL_VERDICT=PASS_BOUNDED_MILESTONE_C_PRIVATE_FIXTURE
OPENRECOMP_PHASE11_HERCULES_GPU_COMMAND_PROOF=PROVEN
OPENRECOMP_PHASE11_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN
OPENRECOMP_PHASE11_HERCULES_FRAME_PROOF=NOT_PROVEN
OPENRECOMP_PHASE11_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN
OPENRECOMP_PHASE11_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN

## Inherited frontier (from Phase 10)

- milestone A: translated native execution begins (PROVEN, `P10-05`/`P10-11`);
- 110 translated functions; deterministic native run; original MIPS machine
  code never executes;
- first fail-closed event: an executed unresolved indirect jump inside the
  initialisation path;
- the reached loop is a served busy-poll loop (GPU status and timer1 counter
  read exactly one-to-one, 109035 each), not a frame loop;
- 65536 recorded GPU events, all GP1 status reads returning the audited
  `GPUSTAT_STUB` `0x14802000`; zero GP0/GP1 command writes;
- the GPU status stub A/B experiment shows identical access traffic, so GPU
  status polling is not the causal blocker;
- interrupt/DMA/memory-control behaviour remains fail-closed;
- CD-ROM reached register-level command traffic only; no disc-data path;
- controller data port never touched; SPU configuration only;
- milestones B .. G remain NOT_PROVEN.

## Stage status

| Stage | Status |
|---|---|
| P11-00 | PASS |
| P11-01 | PASS |
| P11-02 | PASS |
| P11-03 | PASS |
| P11-04 | PASS |
| P11-05 | PASS |
| P11-06 | PASS |
| P11-07 | PASS (bounded blocker) |
| P11-RC | PASS (authorized control-only reconciliation) |
| P11-08 | NOT EXECUTED — no stage verdict assigned |
| P11-09 | NOT EXECUTED — no stage verdict assigned |
| P11-10 | NOT EXECUTED — no stage verdict assigned |
| P11-11 | NOT EXECUTED — no stage verdict assigned |
| P11-12 | NOT EXECUTED — no stage verdict assigned |
| P11-90 | PASS (whole-regression gate, 262 checks, deterministic twice) |
| P11-91 | PASS (evidence closure and proof matrix, 385 checks, deterministic twice) |
| P11-99 | PASS (final bounded verdict, 143 checks, deterministic twice) |

## Stage records

### P11-99 — final bounded verdict

PASS (143 checks). Gate `tools/test_phase11_final_verdict_v1.py` ran twice
through the Phase-11 stage runner with byte-identical stdout (422 raw
bytes, SHA-256 `cd673fda...`), empty stderr, exit 0 and byte-identical JSON
sidecars.

- the frozen Phase-10 terminal boundary is re-verified untouched: commit
  `8961682a` tree `4a58d923`, branch tip `phase10/ps1-commercial-game-native-v1`,
  and the `.openrecomp-phase10` subtree is byte-identical to the historical
  terminal commit;
- every required Phase-11 stage (`P11-00` through `P11-07`, `P11-RC`,
  `P11-90`, `P11-91`) is verified `PASS` with two byte-identical official
  runs, empty stderr, exit 0, its gate marker present, no `FAIL:` line and a
  `PASS` tests record;
- the `P11-91` proof matrix and claim ledger verify: highest proven
  milestone `C`, milestones `B`/`D`/`E`/`F`/`G` `NOT_PROVEN`, the exact
  unresolved `B0:0x57` `GetB0Table` frontier at `0x80015fa4` block `468341`
  `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE`, the four reserved markers and the
  permanent general-PS1 non-claim;
- the exact private fixture identity and the milestone-C GPU evidence
  (required GP0 write `0x0002a244`, known `NOP`) match the committed
  records;
- the scope guards keep the four reserved markers `NOT_PROVEN` and the
  permanent general-PS1 non-claim, and the public-safety verification is
  clean;
- the terminal verdict is bounded: `PASS` for the evidence closure and
  milestone-C private-fixture-bounded claim only; no milestone is promoted
  and no reserved marker is changed;
- evidence: `.openrecomp-phase11/evidence/P11-99/`.

### P11-91 — evidence closure and bounded proof matrix

PASS (385 checks). Gate `tools/test_phase11_evidence_closure_v1.py` ran
twice through the Phase-11 stage runner with byte-identical stdout (23157
raw bytes, SHA-256 `3eedfc0e...`), empty stderr, exit 0 and byte-identical
JSON sidecars.

- every completed stage (`P11-00` through `P11-07`, `P11-RC`, `P11-90`) is
  verified as committed deterministic evidence: byte-identical two-run
  official stdout, no `FAIL:` line, the stage's own gate marker, identical
  sidecars, an uncommitted-diff-free gate script, and a `PASS` tests record;
- the exact pinned facts from every completed stage are cross-checked
  directly against their committed JSON (fixture hashes; the `P11-01` causal
  site `0x80026ccc`/`ps1.bios.A0.2b`; the `P11-05` required GP0 write
  `0x0002a244`; the `P11-06` `EXACT_CONSTANT_TARGET` `0x8001a7dc`; the
  `P11-07` `B0:0x57` `GetB0Table` contract and the exact caller frontier
  `0x80015fa4`/block `468341`/`BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE`; the
  `P11-RC` authorized route; the `P11-90` reconciled claims);
- a 185-file evidence index, a bounded proof matrix (milestones A-G,
  highest proven milestone C, the exact unresolved `B0:0x57` frontier, the
  deliberate `P11-08`..`P11-12` exclusions, the permanent non-claim, the
  four reserved markers) and a claim ledger (every claim keyed to its
  supporting stage evidence) are produced;
- a tracked-evidence private-payload and host-path safety scan reports zero
  violations across 185 scanned files;
- no runtime, BIOS, translation, emission or device behavior changes; no
  milestone is promoted; the four reserved markers remain `NOT_PROVEN` and
  the already-promoted GPU command-proof marker is verified unchanged;
- evidence: `.openrecomp-phase11/evidence/P11-91/`.

### P11-90 — reconciled whole-project regression

The first execution stopped FAIL under `EVIDENCE_INTEGRITY_FAILURE`: in an
isolated worktree at the exact frozen Phase-10 branch, commit and tree, the
unchanged frozen P10-90 regression passed the frozen P10-00 branch assertion
but its Phase-1 host harness failed source integrity because that checkout
lacked the pre-existing untracked `tools/test_build_package_reproducibility_v1.py`
file listed in the frozen root `SOURCE_SHA256SUMS.txt` (the original worktree
copy matches the recorded SHA-256
`2b9b09386c6f530f41b4cfe3b8d9dec868ae858603e5b0bc54ae8f5c37691085`; the
isolated harness reported 43 PASS, one FAIL and two toolchain skips). That
failed attempt is preserved under
`.openrecomp-phase11/evidence/P11-90/initial-failed-attempt/`.

The blocker was resolved only by the audited verification-context recovery
defined in `CONTROL_POLICY.md` ("P11-90 verification-context recovery"): the
28 hash-pinned untracked Phase-2 files were materialized in the isolated
worktree exclusively from their tracked pre-untracking Git blobs at
`b9356999`, with blob ids, lengths and SHA-256 values recorded, the frozen
aggregate residue digest verified, and no ambient-worktree byte source and no
tracked modification.

After recovery the gate `tools/test_phase11_whole_regression_v1.py` ran twice
with byte-identical stdout (17588 raw bytes, SHA-256 `2f18d76d...`), empty
stderr, exit 0 and byte-identical sidecars: `OPENRECOMP_P11_90=PASS` with 262
checks. The gate re-executes the frozen Phase-1..Phase-10 whole regression
live in the isolated worktree (155 checks), re-executes P11-00 through P11-07
live into scratch evidence (P11-02 at 1471 and P11-03 at 1331 checks against
their current shared-contract identities; the other six against their
committed official stdout), verifies P11-RC as a committed deterministic
boundary (179 checks), pins the P11-02 repair to exactly the two
proven-metadata expectation lines, and scans tracked P11-00..P11-RC evidence
for private-payload and host-path leaks.

- the P11-02/P11-03 current identities are metadata-only enrichments from the
  proven P11-07 `B0:0x57` `GetB0Table` public name; both sites remain
  `BIOS_VECTOR_NOT_IMPLEMENTED` / `FAIL_CLOSED` with `op_name` and
  `service_id` null;
- all four proof markers remain `NOT_PROVEN` and milestone C remains the
  highest proven milestone;
- P11-91 and P11-99 are not started and may begin only after this
  predecessor commits successfully.

### P11-RC — authorized bounded terminal-route reconciliation

PASS (179 checks). The required control decision is
`QUEUE_RECONCILIATION_REQUIRED`; the user explicitly authorized the route
`P11-RC -> P11-90 -> P11-91 -> P11-99` from baseline commit
`515e3fb0e660d3c7975e3828eb3e26ac025c7cf2`.

The gate `tools/test_phase11_queue_reconciliation_v1.py` ran twice through
the Phase-11 stage runner with byte-identical stdout (16009 raw bytes, LF
SHA-256 `432963df...`), empty stderr, exit 0 and byte-identical sidecars. The
unchanged P11-00, P11-07, P11-06 and P11-05 gates also pass twice at 482, 41,
75 and 294 checks respectively, and source integrity passes with 23 entries.

- every committed file under evidence `P11-00` through `P11-07` must remain
  byte-for-byte unchanged;
- the exact forcing dependency is the P11-07 `B0:0x57 GetB0Table` frontier at
  `0x80015fa4`, block 468341, whose caller requires a callable guest B0:0x5B
  target plus writable target-relative state not established by acceptable
  public evidence;
- the blocker is architectural/evidentiary, not a CPU, translation, ABI,
  memory, service-state or runtime implementation defect;
- the original P11-08 through P11-12 queue rows remain verbatim, while those
  stages are recorded as not executed with no stage verdict assigned;
- no runtime, BIOS, semantic, translation, emission, guest-memory, device or
  control-flow behavior changes;
- milestone C remains the highest proven milestone and is exact-private-
  fixture bounded; B and D through G remain `NOT_PROVEN`, and general PS1
  compatibility remains permanently `NOT_PROVEN`;
- a licensed replacement-BIOS integration is a future-phase option requiring
  a new control plane, branch, architecture/license review and explicit user
  authorization; it is outside Phase 11.

Evidence target: `.openrecomp-phase11/evidence/P11-RC/`.

### P11-07 — B0:57 public contract and bounded first-frame blocker

PASS, rigorously bounded with `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE`
(41 checks). Gate `tools/test_phase11_b0_table_v1.py` ran twice through the
Phase-11 stage runner with byte-identical stdout (2548 raw bytes, LF SHA-256
`db460f21...`), empty stderr, exit 0 and byte-identical sidecars. The
unchanged P11-06 and P11-05 dependency gates also pass twice at 75 and 294
checks.

- pinned public evidence records PSX-SPX revision `f37fc9a...`, PCSX-Redux
  `911271b7...` with OpenBIOS/nugget `77adff51...` under MIT, and the
  independently structured GPL-2.0 PCSX HLE source at `7787631c...`;
- the established contract is only: `B0:0x57` `GetB0Table`, no arguments,
  mutable word-indexed B0 jump-table guest pointer in `$v0`, with no GPU,
  renderer, DMA, VRAM, interrupt, timing or frame behavior;
- the exact private caller first reads the 32-bit B0:0x5B entry at offset
  `0x16c`, derives pointers at target-relative offsets `0x884` and `0x894`,
  then clears eleven target-relative words at offsets `0x594..0x5bc`; PSX-SPX
  independently documents this pattern;
- the caller therefore requires a guest B0:0x5B function target and internal
  writable layout, not merely a stable table pointer; public sources do not
  establish a portable guest target object that can be represented without
  inventing a pointer or importing/executing BIOS code;
- no B variant is constructed: B0:57 gains only its public name in the
  existing index classification and remains `BIOS_VECTOR_NOT_IMPLEMENTED` /
  `FAIL_CLOSED`; no runtime service, table, indirect target or device behavior
  is added;
- the exact frontier stays `0x80015fa4`, block index 468341; no valid next
  dynamic frontier is established and milestone D remains `NOT_PROVEN`;
- evidence: `.openrecomp-phase11/evidence/P11-07/`.

### P11-06 — GPU/DMA/VRAM semantic closure

PASS (75 checks). Gate `tools/test_phase11_gpu_closure_v1.py` run twice
through the Phase-11 stage runner with byte-identical stdout (3273 raw bytes,
LF SHA-256 `e93cf4cc...`), empty stderr, exit 0 and byte-identical sidecars.
The unchanged P11-05 direct-dependency gate also passes twice at 294 checks.

- the P11-05 runtime target `0x8001a7dc` is proven by the exact RAM pointer
  chain (`0x8002a284` -> `0x8002a244`, field +16 at `0x8002a254`) and is an
  independently decoded entry;
- extending the frontier adds exactly 10 reachable words, one function and one
  block; the existing exact-target machinery resolves `0x8001882c` with a
  guarded dispatch and no general semantic change;
- the newly translated guest function loads the initial `0x1f801814` GP1
  pointer and reaches the frozen typed boundary with `0x03000001`, which the
  frozen classifier records as known `DISPLAY_ENABLE`; it then performs one
  guest RAM bookkeeping byte write;
- the causal prefix A/B is byte-identical through 468323 block events; at full
  budget B adds exactly one ordered known GP1 write, one guest RAM write and
  zero host/service calls; no renderer, DMA, VRAM or interrupt behavior is
  added;
- the ordered GPU write transcript is GP0 `0x0002a244` / `NOP`, then GP1
  `0x03000001` / `DISPLAY_ENABLE`, both known and non-emulated;
- the exact new frontier is fail-closed `B0:0x57` at `0x80015fa4`, source
  `0x000000b0`, block index 468341; its service identity/contract is not in the
  current documented surface and no behavior is inferred;
- evidence: `.openrecomp-phase11/evidence/P11-06/`.

### P11-05 — GPU command-stream frontier

PASS (294 checks). Gate `tools/test_phase11_gpu_v1.py` run twice through the
Phase-11 stage runner with byte-identical stdout (12416 raw bytes, LF SHA-256
`7a860bea...`), empty stderr, exit 0 and byte-identical JSON sidecars. The
frozen P11-04 gate was also run unchanged twice: 851 checks PASS, identical
stdout, empty stderr and exit 0.

- diagnostic classification `GUEST_VALUE_CONFIRMED`: native and reference
  agree on the documented `A0:0x49` call and `$a0 = 0x0002a244`; the argument
  is a stable RAM-derived pointer with zero overlapping writes before the call,
  not a CPU, translation, ABI, memory or runtime-state defect;
- the documented one-argument, void `GPU_cw` service is lowered to a normal
  host call and implemented only as
  `or_rt_memory_write(P9_GP0_ADDR, 32, command)`; the frozen Phase-9 typed GPU
  boundary and classifier are reused unchanged;
- public original synthetic fixtures prove known-NOP ordering and
  classification, void return/control flow, unknown opcode rejection,
  malformed-call rejection and absence of fabricated rendering, VRAM, DMA,
  interrupt or unrelated device state;
- at the causal prefix A and B have the same 468287 block events and digest,
  registers, RAM and device state; B differs only by +1 host/service call, +1
  checked access, +1 non-RAM signature and the genuine typed GP0 write
  `0x0002a244`, classified opcode `0x00` / `NOP` / known;
- milestone C is **PROVEN** for the exact private fixture; milestones B, D and
  G remain `NOT_PROVEN`;
- the exact new frontier is an unresolved indirect call at `0x8001882c`
  (`jalr`, source `0x8001a7dc`) in `blk_80018824` / `fn_800187b0`, block index
  468323;
- evidence: `.openrecomp-phase11/evidence/P11-05/`.

### P11-04 — Milestone B: initialization completion

PASS (851 checks). Gate `tools/test_phase11_initialization_v1.py` run twice
through the Phase-11 stage runner with byte-identical stdout (30792 bytes LF,
sha256 `448c9dcb...`), empty stderr and exit 0. Milestone B is **NOT**
promoted.

- the frozen Phase-3 code frontier is re-run from the statically proven
  driver-method entry `0x80016384` and merged with the inherited frontier
  (4068 + 264 = 4332 reachable words, 682 delay slots, records must agree
  exactly); the merged structure has 121 functions and 793 blocks;
- the P11-03 driver-method indirect call is resolved with
  `EXACT_CONSTANT_TARGET` evidence and emitted through the additive guarded
  dispatch (`default: or_fail("indirect target outside proven set")`);
- two newly reachable op types (`nor`, `sllv`) receive architecture-exact
  additive rules, independently verified with a boundary case;
- public synthetic native fixtures verify the guarded dispatch both ways and
  the two rules;
- the frontier moves again to the documented `A0:0x49` GPU_cw vector call at
  `0x8001b424` (block index 468286); the exact remaining blocker is recorded
  and milestone B remains `NOT_PROVEN`;
- documented divergence: the additive semantics surface grew, so the P11-02
  gate rule-count expectation is now surface-relative (labels and stdout
  unchanged); the committed P11-02/P11-03 sidecars remain historically
  accurate and are not rewritten;
- evidence: `.openrecomp-phase11/evidence/P11-04/`.

### P11-03 — Event / interrupt / DMA progress contract

PASS (1329 checks). Gate `tools/test_phase11_event_contract_v1.py` run twice
through the Phase-11 stage runner with byte-identical stdout (48327 bytes LF,
sha256 `b682cbcb...`), empty stderr and exit 0.

- the documented `A0:0x3f` printf service is served (bounded documented
  subset, no console, documented character-count return; malformed or
  unsupported conversions and excess varargs fail closed) and verified by
  seven public synthetic native fixtures;
- deterministic execution-budget bisection places the first fail-closed event
  at access 506040 with zero device-port accesses and zero non-RAM signatures:
  the whole progress to the frontier is RAM-only, so no interrupt, DMA, timer
  or memory-control behaviour is proven necessary (zero implementation delta);
- the event-relevant documented services (`C0:0x02`/`0x03`/`0x0a`,
  `B0:0x12`/`0x13`/`0x4a`/`0x4b`) stay fail-closed and are not reached before
  the frontier;
- the new exact frontier is the driver-method indirect call at `0x80016204`
  in `fn_800161ec` (block index 468281) with the statically initialized method
  pointer `0x80016384` (driver structure `0x80029624`, field offset 12, the
  pointer occurs exactly once in the image and starts with a function
  prologue but was never discovered by the static CFG);
- evidence: `.openrecomp-phase11/evidence/P11-03/`.

### P11-02 — Dynamic indirect-control frontier

PASS (1466 checks). Gate `tools/test_phase11_indirect_v1.py` run twice through
the Phase-11 stage runner with byte-identical stdout (52783 bytes LF, sha256
`dc4640b4...`), empty stderr and exit 0.

- exact BIOS vector classification of all 19 reachable indirect sites (calls
  and jumps) using the audited convention (vector base in `$t2`, function index
  in the delay slot): 1 resolved service (`ps1.bios.A0.2b`) and 18
  documented-but-unimplemented indices that stay fail-closed and are never
  renamed; invalid proof claims are rejected by the shared classifier;
- the causal site `0x80026ccc` is emitted as an explicit host call
  (`jump_bios_a0_2b`) with the audited argument/return registers and served by
  a typed host-side memset implemented through the frozen checked memory
  boundary; the runtime composition keeps the Phase-10 composition verbatim
  except two anchored substitutions and the appended BIOS fragment;
- public synthetic native fixtures verify the contract: fill with a non-zero
  byte and exact length, refusal on `dst == 0` and `len == 0`, fail-closed on
  an out-of-range destination and on an unimplemented vector index;
- the frontier moves from `0x80026ccc` (block index 9424) to `0x80026cec`
  (`A0:0x3f` printf) at block index 468147 (a gain of 458723 clean block
  entries) with the instrumented run reproducing the uninstrumented
  observables exactly;
- a deterministic 8,000,000 block-entry budget closes the recorded Phase-10
  bounded-execution gap (the default-budget run terminates via the bound);
- evidence: `.openrecomp-phase11/evidence/P11-02/`.

### P11-01 — Milestone-A progress causality

PASS (583 checks). Gate `tools/test_phase11_causality_v1.py` run twice through
the Phase-11 stage runner with byte-identical stdout (21907 bytes LF, sha256
`4e9fb85d...`), empty stderr and exit 0.

- additive, opt-in instrumentation in `openrecomp/host_emitter.py`
  (`HostInstrumentation`: function-entry, block-entry and indirect-failure
  hooks); disabled output is byte-identical to the frozen program fingerprint
  `a047a52f...`; the fail-closed `or_fail` call is always preserved; invalid
  hook names and empty configurations fail closed; four live direct-dependency
  emitter/translation gates pass;
- instrumented emission: 110 function hooks, 739 block hooks, 40
  indirect-failure hooks; no guest payload bytes and no opcode dispatch;
- trace semantics equivalence: the instrumented run reproduces every
  uninstrumented guest observable exactly (reads 982859, writes 799023,
  denied 11, host calls 79, RAM digest `0x18131c6ef356df7d`, device counts and
  digests, register file); two builds and two runs are byte-identical;
- exact causal frontier: the first fail-closed event is an executed unresolved
  indirect jump at `0x80026ccc` in `fn_80026cc8` (block index 9424, guest
  access index 9430, 31 fail-closed indirect events in total), and the site is
  a PS1 BIOS A0 jump-table call (`$t2` = `0x000000a0`; delay-slot
  `addiu $t1,$zero,43`; service id `ps1.bios.A0.2b`) classified with the
  frozen audited BIOS-boundary helpers; no BIOS service is implemented;
- independent execution-budget bisection: the first failure occurs at access
  9430 (budget 9429 fails earlier with a budget denial; budget 9430 reports
  the unresolved indirect jump with zero device traffic and zero non-RAM
  signatures); device traffic first appears between accesses 400000 and
  500000, so the whole Phase-10 device frontier (CD-ROM 38, SPU 5, GPU status
  and timer1 polling 109035 each) is post-failure;
- loops: the pre-failure loop is the guest's own terminating BSS-clear loop
  (`blk_800132f8`, 9416 iterations); the persistent post-failure loops are a
  458,711-entry RAM word-fill loop (`blk_80011c14`, `fn_80011bcc`) and a
  14-block, 54,501-iteration GPU/timer poll cycle in
  `fn_80015810`/`fn_80015ff8` governed by `blk_800158a8` (`bgtz`);
- analysis cache: the frozen Phase-10 provenance-keyed cache with the extended
  Phase-11 provenance (trace configuration and scripted-input identity in the
  key); stale trace configuration, changed input identity and changed
  executable identity all miss;
- evidence: `.openrecomp-phase11/evidence/P11-01/`.

### P11-00 — Phase-11 boundary + control plane

PASS (482 checks). Gate `tools/test_phase11_boundary_v1.py` run twice through
the Phase-11 stage runner with byte-identical stdout (17748 bytes LF, sha256
`5bb0760d...`), empty stderr and exit 0.

- frozen Phase-10 terminal boundary verified: commit
  `8961682aa36e14db979e8e8dbe88e04fa2b4c87a`, tree
  `4a58d9238d76a490560c588bb470fd9e6a58cafe`, 25 frozen control/terminal
  hashes, the 135-file Phase-10 evidence index verified file-by-file, all 16
  Phase-10 stage records `PASS` with `failed=0` and terminal counts `P10-90`
  155 / `P10-91` 323 / `P10-99` 166 (2277 recorded checks), the frozen
  Phase-9 and Phase-10 source manifests unchanged, and the inherited tag
  reconciliations intact;
- private fixture/disc identity re-verified exactly (`SLUS_005.29`
  `c230ff5c...`, CUE `beea454d...`, BIN `2ce144ba...`, ISO9660 space size
  174087, root extent LBA 22, boot extent byte-identical to the executable);
- frozen structure and emission identities reproduced live (3433 neutral
  instructions, 739 blocks, 110 functions, program fingerprint `a047a52f...`,
  image unit `77a34044...`, no guest payload bytes, no opcode dispatch);
- milestone A reproduced live: two isolated builds byte-identical, two native
  runs byte-identical, `failed=1`, `error=unresolved indirect jump`,
  reads 982859, writes 799023, denied 11, host calls 79, access count 2000005
  against budget 2000000, RAM digest `0x18131c6ef356df7d`, GPU status 109035
  and timer1 109035, and the crt0-observable register values;
- inherited non-claims re-verified: B..G not established, zero GPU command
  writes, GPU status polling non-causal (A/B identical traffic), no disc data
  path, no controller access, no frame loop;
- Phase-11 control plane, policies, evidence schema and frozen queue
  (`P11-01` .. `P11-99`), source manifest and stage runner created;
- no substantive compatibility implementation; all four claim markers remain
  unpromoted;
- evidence: `.openrecomp-phase11/evidence/P11-00/`.

## Working-tree residue (preserve untouched)

Tracked Phase-3 evidence files under `.openrecomp-phase3/evidence/P3-00/` are
modified by a historical verification-context re-run, and untracked residue
exists under `.openrecomp-phase2/`, `.openrecomp-phase3/`, `artifacts/` and
`tools/test_build_package_reproducibility_v1.py`. This residue predates Phase
10 and must never be committed, deleted or altered by Phase-11 work.

## Open blockers

- `P11-07`: `BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE` — the caller requires the
  B0:0x5B guest function pointer and a valid writable function-relative object.
  Public sources establish the lookup and patch offsets but not a portable
  guest target representation compatible with the no-BIOS-runtime scope.
- `P11-RC`: queue reconciliation passed. The next authorized work is
  evidence-only `P11-90`; no permission exists to start or simulate `P11-08`
  through `P11-12`.
