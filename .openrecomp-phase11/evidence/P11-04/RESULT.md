# P11-04 result: Milestone B — initialization completion

Status: `PASS` (851 checks)

Markers:

- `OPENRECOMP_P11_04=PASS`
- `OPENRECOMP_PHASE11_INITIALIZATION_V1=PASS tests=851`
- `OPENRECOMP_PHASE11_HERCULES_INITIALIZATION_PROOF=NOT_PROVEN` (milestone B not crossed)
- `OPENRECOMP_PHASE11_HERCULES_FRAME_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE11_HERCULES_PLAYABILITY_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE11_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase11_initialization_v1.py`.

## Milestone B: NOT promoted

Initialization does not complete. The exact next fail-closed event is the
documented **`A0:0x49` GPU_cw** BIOS vector call at `0x8001b424` in
`fn_8001b420`; milestone B is therefore **not** promoted and the claim remains
`NOT_PROVEN`.

## Additive capabilities (all default-off; frozen output unchanged)

| File | Change |
|---|---|
| `openrecomp/host_emitter.py` | additive `nor` and `shlv` binop kinds; additive `guarded_resolved_indirect` config flag (emits the value-checked switch even for a single resolved target) |
| `.openrecomp-phase11/src/p11_dynamic_v1.py` | frontier extension + dynamic target resolution |
| `.openrecomp-phase11/src/p11_structure_v1.py` | multi-entry structure overlay (BIOS op renames + dynamic targets) |
| `.openrecomp-phase11/src/p11_semantics_v1.py` | additive `nor`/`sllv` rules |

The disabled default is byte-identical to the frozen program fingerprint
`a047a52f...`, and the frozen `or_fail`/single-target emission paths are
unchanged.

## Frontier extension (statically proven driver-method entry)

The P11-03 blocker was an indirect call whose source pointer
`0x80016384` is a statically initialized image value (driver structure
`0x80029624`, field offset 12). The frozen Phase-3 code frontier is re-run from
that entry point and merged with the inherited frontier:

| Item | Value |
|---|---|
| base entry | `0x800132e8` |
| base reachable words | 4068 |
| extra entry | `0x80016384` |
| extra reachable words | 281 (264 new) |
| merged reachable words | 4332 |
| delay slots | 682 |
| record count | 31744 |

Merged structure: **121 functions** (110 + 11), **793 blocks**. Records must
agree exactly between the two runs (decoder fields, excluding reachability)
and the delay-slot sets must be consistent; unaligned entries, out-of-region
entries and unreachable observed targets all fail closed.

## Dynamic target resolution

The site `0x80016204` (`jalr $v0` in `fn_800161ec`) is resolved with
`EXACT_CONSTANT_TARGET` evidence (observed deterministically at runtime; the
observed target is a reachable instruction boundary) and emitted through the
guarded dispatch: `switch (value) { case 0x80016384: call; ...; default:
or_fail("indirect target outside proven set"); }`. Any other runtime pointer
fails closed. No target is guessed.

## Newly reachable op types (independently verified)

Two op types only become reachable through the proven entry: `nor` and `sllv`.
Both receive architecture-exact additive rules, verified by independent Python
computation and a boundary case (`nor(0x0F0F0F0F, 0x00FF00FF) = 0xF000F000`;
`sllv` with a shift of 33 masks to 1, so `1 << (33 & 31) = 2`).

## Public synthetic fixtures

| Fixture | Result |
|---|---|
| guarded dispatch, proven target | `failed=0`, target called, `$v0` = 2 |
| guarded dispatch, other pointer | fail-closed `indirect target outside proven set` |
| `nor` rule | `$v0` = `0xf000f000` |
| `sllv` rule (shift 3) | `$v0` = 8 |
| `sllv` mask boundary (shift 33) | `$v0` = 2 (MIPS 5-bit shift mask) |

## New exact frontier

| Item | Value |
|---|---|
| site | `0x8001b424` (`jr $t2`) in `fn_8001b420` |
| message | `unresolved indirect jump` |
| source | `$t2` = `0x000000a0` → documented `A0:0x49` GPU_cw |
| block index | 468286 (24 fail-closed indirect events total) |
| host calls | 83, `p10_service_failures=0` |
| CD-ROM events | 33, SPU 0 |
| block entries | 8000001 (deterministic block budget reached) |

## Frontier movement

| Stage | First fail-closed event | Clean progress |
|---|---|---|
| P11-01 | `0x80026ccc` (memset) | 9424 block entries |
| P11-02 | `0x80026cec` (printf) | 468147 block entries |
| P11-03 | `0x80016204` (driver method call) | 468281 block entries |
| P11-04 | `0x8001b424` (`A0:0x49` GPU_cw) | 468286 block entries |

## Documented divergence (correction trail)

The Phase-11 additive semantics surface grew during P11-04 (`nor`, `sllv`).
Consequences for earlier stage records, recorded here rather than silently:

- the P11-02 gate's rule-count expectation is now *surface-relative*
  (`len(phase10 rules) + len(p11_semantics.added_rules()) + 1`); its check
  **labels and printed stdout are unchanged**, so the committed P11-02
  `run1.txt`/`run2.txt`/`official_runs.json` remain byte-valid;
- the committed P11-02 `frontier.json` and P11-03 `frontier.json` sidecars
  embed the semantics document of the composition at their stage and remain
  historically accurate; a live re-run now reports `rules_total=50` instead of
  48. The committed sidecars are deliberately **not** rewritten
  (Phase-10 `P10-07`/`P10-90` precedent: gate stdout identity is the audited
  contract; sidecars record the composition at their stage);
- no earlier conclusion or milestone verdict is affected.

## Official runs

Command `python .openrecomp-phase11/src/p11_stage_runner_v1.py --stage P11-04
--script tools/test_phase11_initialization_v1.py --evidence-dir
.openrecomp-phase11/evidence/P11-04 --tests-json p11_04_tests.json`, exit 0,
empty stderr, both runs byte-identical: stdout 31649 bytes raw / 30792 bytes
LF, sha256 (LF) `448c9dcbda12e210c8c157d80e43f0e4e8c236eac34c9344a98733c9f9ac803b`;
generated evidence sidecars byte-identical across both runs.

Sidecar identities:

- `frontier.json` `42117d0ddc24dd7bc87b7f9c6e6b54b4aa736e891e2984692cd766987b5eed78`;
- `p11_04_tests.json` `24a62a548fbe0c06f4b13fcd299acf438179dac14a0c2f831bc85045e7b1434c`;
- `official_runs.json` `ed5299c3152e0ce72256d579ef10bc69767ab3542ee7fe4bdef92c7924c7668b`;
- `determinism.json` `47681c1f70c8e4547740db142d9a5032b38781036db015eb532e280ab625c1f8`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Public safety

The committed record contains addresses, identifiers, counts, classifications,
documented function names, digests and gate results only. The public-safety
scan (payload hex, base64, printable ASCII runs, string length) passes. No
payload bytes, no disassembly excerpts, no strings, no sectors, no framebuffer
or VRAM content and no absolute host paths are present.

## Claim-ledger delta

`PROVEN`: the statically proven driver-method entry, the frontier extension,
the guarded dynamic resolution, the two additive op rules (independent
verification) and the next exact blocker. `BOUNDED` (private only): the
single-fixture frontier. Initialization completion, GPU command stream,
frames, title/menu, gameplay, playability and general PS1 compatibility remain
`NOT_PROVEN`.

## Next stage

`P11-05` - GPU command-stream frontier: classify the exact `A0:0x49` GPU_cw
request (command word provenance, call site, register state), determine
whether it is causal for progress, and implement only the evidence-required
behaviour through the frozen typed GPU boundary; unknown commands stay
fail-closed and milestone C is promoted only if genuine GPU command writes are
reached and classified deterministically.
