# P9-91 result: evidence closure and claim ledger

Status: `PASS` (181 checks)

Markers:

- `OPENRECOMP_P9_91=PASS`
- `OPENRECOMP_PHASE9_EVIDENCE_INDEX_V1=PASS tests=181`
- `OPENRECOMP_PHASE9_PS1_PLATFORM_RUNTIME_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` (permanent)
- `OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase9_evidence_index_v1.py`.

## Stage-record closure

Every completed Phase-9 stage (`P9-00` .. `P9-12`, `P9-90`) has a `RESULT.md`,
a machine-readable tests record with `status: PASS` and `failed: 0`, and an
`official_runs.json` with two byte-identical runs, empty stderr and exit 0.
Every sidecar hash recorded in `official_runs.json` matches the file on disk.

## Evidence index

`evidence_index.json` covers every committed Phase-9 evidence file except this
stage's own generated sidecars: 141 entries, exact SHA-256 and byte sizes,
grouped by stage. The live index equals the committed index.

## Claim ledger

`claim_ledger.json` classifies every Phase-9 claim with the vocabulary
`PROVEN` / `BOUNDED` / `NOT_PROVEN` / `NOT_TESTED`:

- `PROVEN` (13 claims): PS-X EXE ingestion (bounded V1 form); explicit PS1
  address-space contract; frozen MIPS32 pipeline reuse; reachable translation
  closure; typed fail-closed BIOS/service boundary; non-emulating GPU adapter
  boundary; deterministic input/time interfaces; SPU audio contract; CD-ROM
  file-service contract; native recompilation and deterministic execution;
  independent reference equivalence; private Hercules bounded validation;
  fail-closed hardening and reproducibility.
- `BOUNDED` (3 claims): platform port behaviour is event recording / contract
  stubs rather than hardware emulation; private-fixture discovery is exact only
  within the bounded same-block windows; the flat 2 MiB RAM and explicit stack
  window model.
- `NOT_PROVEN` (10 claims): general PS1 compatibility, arbitrary PS-X EXE
  compatibility, BIOS emulation, GPU rendering, SPU synthesis, CD-ROM disc
  reading, controller protocol, interrupt delivery, COP0/GTE execution,
  Hercules playability.
- `NOT_TESTED` (1 claim): memory cards, DMA and link cable behaviour.

The permanent non-claims
`OPENRECOMP_PHASE9_GENERAL_PS1_COMPATIBILITY=NOT_PROVEN` and
`OPENRECOMP_PHASE9_HERCULES_PLAYABILITY=NOT_PROVEN` are recorded and the
terminal claim remains reserved as `NOT_PROVEN` at this stage.

## Public safety

The public-safety verification scanned every indexed evidence file: no private
payload material (hex, base64 or ASCII runs) and no absolute host paths. The
private fixture is explicitly not a `PASS` criterion.

## Official runs

Command `python .openrecomp-phase9/src/p9_stage_runner_v1.py --stage P9-91
--script tools/test_phase9_evidence_index_v1.py --evidence-dir
.openrecomp-phase9/evidence/P9-91 --tests-json p9_91_tests.json`, exit 0,
empty stderr, both runs byte-identical: stdout 5848 bytes (LF), sha256
`7323e6999eb210505ae1c6dc9199d01a8d75bddca9c5caff1cf2028a8b9eac24`.

Sidecar identities:

- `p9_91_tests.json` `55ce64a506ac1636958c2b47031950a16be79b5e7e628ecc1a267ba7bdfa99fd`;
- `evidence_index.json` `894cfe39afda68c4bd6a0cb3a7863636f560624b157ef6d04872d84826b5efa4`;
- `claim_ledger.json` `878bb7a25e495b6306d34f928112be13ff2179a0cac1562b5fea563887b791c5`;
- `official_runs.json` `d1d9377a15943a7296d5f37e9c5dda986cf0cd5e5cf07df95976959ffa24d6db`;
- `determinism.json` `0e3ca40c20d2363a65563dabdf4c4495fc2717289459484d16d12cd41e7c9cb1`;
- `run1.txt` = `run2.txt` `7323e6999eb210505ae1c6dc9199d01a8d75bddca9c5caff1cf2028a8b9eac24`;
- `run1.err.txt` = `run2.err.txt` empty
  (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).

## Evidence-hygiene adjustment

The P9-12 safety scan now excludes its own generated sidecars so the scanned
count (and therefore its tests sidecar) is stable across the two official
runs; its official stdout is unchanged (`1e4981ce...`) and the runs were
re-issued. No semantic evidence changed.

## Claim-ledger delta

`BOUNDED`: the Phase-9 evidence chain is closed and indexed, and the claim
ledger is explicit. No terminal claim is issued at this stage.

## Next stage

`P9-99` - final bounded verdict: audit every Phase-9 stage and issue `PASS`
only for the exact evidence-supported PS1 integration claim.
