# P17-04R — Controller independent review (Revision 4)

Decision: **ACCEPT and INTEGRATE** Revision 4 (`0ab4e7eb2ed4393cec7f61a79705d2c44bbc4441`).

## Authority
- controller branch `phase17/ps1-title-overlay-recompile-v1`
- pre-integration controller HEAD `b460a7018a8e828cc47e471bea6a22ccc71b20f6`
- integrated by fast-forward only (no rebase, no cherry-pick)

## Independent controller verification (performed in the rev4 worktree)
- `git status --short` empty at start (`937e5fa0`) and at result (`0ab4e7e`).
- `git diff --name-only 937e5fa0..0ab4e7e` touches 22 paths; zero Phase-1..16 paths (checked: NONE).
- official gate rerun twice from fresh private build roots, evidence written into the worktree evidence dir:
  - run A exit 0; run B exit 0
  - stdout byte-identical between runs
  - regenerated evidence byte-identical between runs
  - regenerated evidence byte-identical to the committed evidence (`diff -rq` clean)
  - `P17-04R_CHECKS=141`, zero non-PASS, `OPENRECOMP_P17_04R_REV4=PASS` in both runs
- persisted private artifacts present after process exit, hashes matching committed evidence:
  `or_title_runtime_v1.c` `f46291c6…`, `private_mapping.json` `963c8eda…`,
  `or_title_runtime_v1` `ecc6bed6…`, `or_title_runtime_v1.so` `a96c112a…`
- authentic frontier: JAL owner `0x8003812c`, delay slot `0x80038130` executed (option A),
  pending `DIRECT_CALL` → `0x80011af0` applied after the delay slot, stop `PC_NOT_IN_AUTHENTICATED_TABLE`,
  executed count 37.
- vocabulary separation: implemented 45, exercised 14 (derived from the 37-entry executed trace),
  exercised ⊆ implemented.
- linkage exclusion: excluded, forbidden hit count 0, negative control detected
  (nm / readelf / objdump on the persisted artifact).

## Rejected alternative
`agent/deepseek-phase17-p17-04r-rev5` (`83cacffa0724401049fd4356ce18a9f116a44b5e`):
canonical dual reruns exit 0 with identical stdout and identical A/B evidence, but the regenerated
`linkage_exclusion.inspection_digest` (`73c249e315aec224b2c22ecdc5bdc8e7d72cb5a468da944538721ca7f6dda766`)
does not reproduce the committed value
(`25d3ed93031eea70c6b37277746db61d093a4d88e5422b592f6ea2d7e6a757fc`), and the regenerated
`RESULT.json` differs on the same field. Its committed evidence is therefore not reproducible from its
own committed source at that HEAD. Not accepted; REVISE required.

## Scope discipline
- No Phase-1..16 file changed.
- Historical P17-04..P17-07 `RESULT` records untouched.
- `NOT_PROVEN` markers preserved; no broader claim promoted.

## Remaining
- Replacement stages **P17-05R**, **P17-06R**, **P17-07R** and terminal gates **P17-90 / P17-91 / P17-99**
  remain outstanding.
