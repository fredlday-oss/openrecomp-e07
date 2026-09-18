# P4-06 result (PASS)

Stage: `P4-06` Graphics/audio abstraction boundary (frozen queue row).
Gate: `tools/test_phase4_graphics_audio_v1.py` (72 checks, sha256
`c4b8698a7ad213beb8f9d30ed2c8d06e43dcdc830185ff5ebae726fa2edbd99e`).
Evidence: `.openrecomp-phase4/evidence/P4-06/`.

Markers issued:

- Stage marker: `OPENRECOMP_P4_06=PASS`
- Gate marker: `OPENRECOMP_PHASE4_GRAPHICS_AUDIO_V1=PASS tests=72`
- Terminal marker (reserved): `OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN`
- General compatibility marker (never promoted):
  `OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN`

## Objective (frozen queue)

Define reusable graphics and audio adapter boundaries suitable for later
backend implementations. Do not make RT64, SDL, Vulkan, Direct3D or any
particular renderer/audio system mandatory to the OpenRecomp core.
Backend-specific integrations may be future adapters only unless explicitly
required and proven by this phase.

## Implementation (additive Phase-4 files only)

- `.openrecomp-phase4/src/p4_graphics_audio_v1.py`:
  - `GraphicsCapabilities`/`AudioCapabilities`: pixel/sample formats (from the
    P2-08 neutral enums), bounded dimensions, sample rates, channels, buffer
    sizes and capacities;
  - `GraphicsBoundary`/`AudioBoundary` adapter interfaces with fail-closed
    submission validation;
  - deterministic reference boundaries `HeadlessGraphics`/`HeadlessAudio`
    recording bounded presentation ledgers (sequence, format, checksum,
    ledger digest) with no output, plus `NullGraphics`/`NullAudio` that
    accept nothing;
  - `GraphicsBoundaryHook`/`AudioBoundaryHook` routing the optional P4-05
    platform hooks into boundaries;
  - contract document/fingerprint (`38077ea2...`) recording
    `renderer_backend_mandatory: false`, `audio_backend_mandatory: false`
    and backend integrations as future adapters only.
- `tools/test_phase4_graphics_audio_v1.py` - the P4-06 gate.
- `.openrecomp-phase4/SOURCE_SHA256SUMS.txt` - grown additively to sixteen
  entries.

## P4-05 stage-internal repair (discovered by this stage)

Binding a minimal-profile adapter exposed a P4-05 defect: `bind_platform`
merged every P4-04 deterministic-I/O handler even when the adapter's service
profile did not declare those interfaces, so binding failed with
`unknown runtime service` instead of binding only the declared interfaces.
Repaired at the source in `p4_platform_adapter_v1.py` (handlers filtered to
the bound registry), the frozen P4-05 gate re-ran twice with byte-identical
stdout (`849af7fd...`, same 76 checks), and the affected P4-05 pins were
refreshed (`determinism.json`, `changed_files.txt`, `repair_record.json`,
`repair_run1/2.txt`, documented in `P4-05/RESULT.md` and `STATE.md`). No
stage contract, queue row or claim changed; the frozen Phase-3 tag is
untouched.

## Frozen-boundary regression hygiene note

The P4-00 boundary re-run required holding out every tracked Phase-4 path
whose working-tree bytes differ from HEAD (manifest, repaired P4-05 module,
P4-05 evidence refresh) in addition to the boundary sidecars. The P4-00 gate
then re-passed with byte-identical stdout (`953312d0...`). Recorded in
`regression_hygiene.json`; this refines the documented hygiene procedure.

## Verification highlights

- `contract:*`: formats from the P2-08 enums, limits, no mandatory backend
  claims, stable fingerprint, no backend tokens in the contract document.
- `graphics-caps:*` / `audio-caps:*`: capability validation positives and
  negatives (unknown formats, zero/oversized dimensions, duplicate rates,
  channel/sample bounds, capacities).
- `graphics:*` / `audio:*`: headless ledgers record exact frame/audio
  checksums; unsupported format/dimension/rate, capacity exhaustion, wrong
  types and invalid capabilities all fail closed; null boundaries reject
  everything; documents/fingerprints deterministic and ledger-sensitive.
- `hooks:*`: boundary hooks are P4-05 hooks; a bound platform adapter
  reports `graphics_hook`/`audio_hook` capabilities, routed submissions land
  in the boundary ledgers, and negative-claims discipline is preserved.
- `independence:*`: no backend tokens in the module; imports are limited to
  neutral stdlib and Phase-4/openrecomp modules.

## Determinism

- Two consecutive official gate runs: exit 0, empty stderr, stdout
  byte-identical raw (2783 bytes, `d2a59e4a...`) and LF (`5350e47f...`), and
  `p4_06_tests.json` byte-identical across both runs (`7e7bd2d5...`).
- Evidence: `official_runs.json`, `determinism.json`.

## Regressions

- P2-08 `PASS tests=169`; P4-01 `PASS tests=156` (`81c96314...`); P4-02
  `PASS tests=113` (`5cfc58f1...`); P4-03 `PASS tests=86` (`cc2f73da...`);
  P4-04 `PASS tests=101` (`e55ad6cb...`); P4-05 `PASS tests=76`
  (`849af7fd...`, post-repair).
- `tools/phase1_host_gates_v1.py` `PASS=44 FAIL=0 SKIPPED=2`.
- `tools/public_safety_scan.py` `OPENRECOMP_PUBLIC_SAFETY=PASS`.
- P4-00 `PASS tests=74` (`953312d0...`) with the refined frozen-gate
  boundary-context hygiene.

## Limitations

- The boundaries are contract + deterministic headless reference
  implementations only; no real renderer, audio system or backend is
  integrated, and none is required by the core.
- Rendering/audio correctness, frame pacing and real device output are not
  claimed and are out of scope for this phase.
- `GENERIC_RUNTIME_STATUS=NOT_PROVEN`; the terminal and general compatibility
  markers stay reserved.

## Next stage

P4-07 - Interactive legally-clean fixture.
