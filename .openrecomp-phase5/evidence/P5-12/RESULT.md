# P5-12 Reproducible NES Package - Result

Verdict: `PASS`

## Baseline

- Branch `phase5/nes-platform-v1` at commit `b3111a0` (P5-11 boundary).

## Objective (frozen queue)

Build a reproducible public package using only redistributable artifacts.
TMNT ROM bytes must not appear anywhere in the package.

## Package

- `.openrecomp-phase5/package/phase5_nes_package_v1.zip`:
  - SHA-256 `447f72cc616d80fa72e3681c5acd34b00833d7e3fe3fb5bf8bf3230347cc4c13`
  - manifest fingerprint
    `dfabe4ffc3517b7782fc85d0a4ed16e640991a33e726664a5dcb32608a4cf298`
  - 169 members, two builds byte-identical.
- Members: the eight Phase-5 control-plane files (`control/`), the original
  fixture assembly (`fixture/`), all fifteen Phase-5 source modules (`src/`),
  all twelve Phase-5 gates except the self-referential terminal gates
  (P5-12/90/91/99) (`gates/`),
  evidence `P5-00` .. `P5-10` (`evidence/`), the deterministic generated
  native translation sources for the canonical declared plan
  (`generated/p5_nes_program.c`, `generated/p5_nes_support.c`,
  `generated/public_fixture_metadata.json`), `REPRODUCE.md` and
  `P5_PACKAGE_MANIFEST.json` (per-member size/sha256 plus canonical
  fingerprint).
- Content policy (fail-closed): every member is UTF-8 with LF endings; no
  binary members; the private TMNT image, a deterministic 256-byte private
  PRG probe slice and the private P5-11 evidence are absent; the P5-11
  evidence directory is excluded by name and checked in-gate.

## Verification

- Byte-identical rebuild and byte-identical manifest across two builds.
- Every member listed in the manifest with matching size/hash; required
  control/source/gate/evidence members present.
- Self-contained rebuild: the packaged generated sources compile with the
  recorded zig 0.13.0 toolchain and reproduce the canonical P5-08 observable
  exactly (`failed=0`, `exit=1`, `steps=90904`, `frames=11`, `nmi=8`,
  `clock=298327`, `state_fnv1a64=0x440A095E452B3BA9`).

## Official gate

- Two consecutive runs: exit 0, empty stderr, stdout byte-identical.
  - stdout: 9812 bytes raw, raw sha256
    `32e4daf71142e3700157b37cd1240b998af259033c1c304177dbf66d452ee58b`,
    LF sha256
    `b5f02035a66ff27915ea6a4536a6c8d284a884a6fcee40d515f47e22944ce035`.
  - `p5_12_tests.json` sha256
    `5a6e89f758a76d4dbc00d4c7b0f2a373fce866ad5ee1c9b2dd5b3b091fc4330e`.
- Markers: `OPENRECOMP_P5_12=PASS`,
  `OPENRECOMP_PHASE5_PACKAGE_V1=PASS tests=190`; terminal/general reserved as
  `NOT_PROVEN`.
- Gate sha256 `ea3258f54c2c6c0a4753bf1602eaaa17aa7bd5efcad0bb714ca7fbb2a7d819fd`;
  Phase-5 manifest verifies all twenty-nine entries.

## Regressions

`tools/test_phase5_tmnt_private_v1.py` (scratch evidence) and
`tools/test_nes_rom_v1.py` re-pass with empty stderr (recorded in
`regressions.json`).

## Limitations

- Reproducibility is bound to this tree state and the recorded external
  toolchains (zig 0.13.0, clang-cl/lld-link), which are not shipped.
- The private P5-11 analysis deliberately stays inside the repository and is
  not redistributed in the package.
- The package proves only the bounded audited public-fixture claim.

## Evidence files

`RESULT.md`, `p5_12_tests.json`, `official_runs.json`, `determinism.json`,
`package_manifest.json`, `verification.json`, `regressions.json`, `run1.txt`,
`run2.txt`, `run1.err.txt`, `run2.err.txt`.

## Next stage

P5-90 - Phase-5 whole regression.
