# P10-11 result: highest Hercules milestone

Status: `PASS` (38 checks)

Markers:

- `OPENRECOMP_P10_11=PASS`
- `OPENRECOMP_PHASE10_MILESTONE_V1=PASS tests=38`
- `OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE10_HERCULES_PLAYABILITY=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE10_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase10_milestone_v1.py`.

## Highest demonstrated milestone: A

| Milestone | Established | Basis |
|---|---|---|
| **A** translated native execution begins | **YES** | `P10-05`: deterministic native run of translated guest code; the guest crt0 effect is observable (`$gp` `0x8002ed78`, `$fp` `0x80200000`, `$sp` `0x801ffe00`); 982859 reads + 799023 writes executed; the guest RAM digest changed; the run fails closed deterministically |
| B initialisation completes | NO | the guest fails closed inside its initialisation path at an executed unresolved indirect jump; no completion evidence exists |
| C GPU command stream reached | NO | only GP1 status reads (109035) are reached; **zero** GP0 and **zero** GP1 command writes |
| D first valid rendered frame | NO | no frame or present observable exists |
| E title/logo screen | NO | no frame and no display output exists |
| F menu reached | NO | no completed initialisation, no frame loop, no menu state reachable |
| G controllable gameplay | NO | the controller data port is never touched; no input-driven state progression exists |

The reached loop is a served busy-poll loop (GPU status and timer1 counter read
exactly one-to-one, 109035 each), not a frame or event loop.

## Evidence binding

Every milestone verdict is derived from, and hash-bound to, the committed stage
evidence, so no claim can outlive its evidence:

| Stage | Sidecar | SHA-256 |
|---|---|---|
| P10-05 | `native_entry.json` | `ef7b834293e4e5ff1067c78154ccbbeac218276bea1375000bd380e3cb6c05e9` |
| P10-07 | `gpu_frontier.json` | `e60c4dc20089bcb7d70d11247ecaadd44b750437c14e3bea3f4fce452632d73a` |
| P10-08 | `timing_frontier.json` | `a2dc8506a5444be019662cb5ae9042483c74b8993ecc9af1a191c5cf1d735eb2` |
| P10-09 | `disc_frontier.json` | `9e8715c489a033b717e5b69607d747c4315c99d0fed11234845fcc49b4ca0896` |
| P10-10 | `input_spu_frontier.json` | `2b697b82813aa14af1f0744e76cb0d534a0dc3a4263544a10e0b6bb5b35bb538` |

## First remaining blocker

The executed unresolved indirect jump (control flow), which precedes any GPU
command write, any controller read and any disc data transfer; the deterministic
access budget is subsequently reached. The exact failing guest PC is not
observable and only the complete candidate set is recorded.

## Playability promotion rule

Milestone G - with deterministic scripted-input evidence of reproducible
game-state progression - is the only evidence that may support a playability
claim. It is absent, so `OPENRECOMP_PHASE10_HERCULES_PLAYABILITY` remains
`NOT_PROVEN` and `OPENRECOMP_PHASE10_HERCULES_NATIVE_EXECUTION_PROOF` remains
reserved for the terminal audit (`P10-99`).

## Official runs

Command `python .openrecomp-phase10/src/p10_stage_runner_v1.py --stage P10-11
--script tools/test_phase10_milestone_v1.py --evidence-dir
.openrecomp-phase10/evidence/P10-11 --tests-json p10_11_tests.json`, exit 0,
empty stderr, both runs byte-identical: stdout 1284 bytes (LF), sha256
`29a3d4a2214a3e7be56c941dabf5a08315aa89d9042654b95a1277a5ee30dbd1`; generated
evidence sidecars byte-identical across both runs.

Sidecar identities:

- `milestone.json` `77dd3edc8aded9dd478b04ad8c6ec9fc47592349e62260660c0ae3744b5d64cd`;
- `p10_11_tests.json` `3e1becdd66d08d71f0a2a260d52fe3bbc086f9d02ba36a8128566d9ee24e6df5`;
- `official_runs.json` `47f95d9dcbe162902170ca87594a02a665e431c723eb9d7cac7862344067e698`;
- `determinism.json` `497f8609ef8d91d21f64e9b9ae44066ded4142e2b8163e6df7513ecb244311c6`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Public safety

The committed record contains milestone verdicts, reasons, evidence hashes,
counts and frontier facts only. No screenshots, framebuffer captures, frames,
audio, payload bytes or disc material.

## Claim-ledger delta

`PROVEN`: milestone A and the explicit non-establishment of B through G.
`BOUNDED` (private only): the single-run evidence chain. Native execution proof
terminal promotion, playability and general PS1 compatibility remain
`NOT_PROVEN` (the first two are decided at `P10-99`).

## Next stage

`P10-12` - hardening and reproducibility.
