# P17-05R — Controller independent review

Decision: **ACCEPT and INTEGRATE** (`b18fd4bee216b3133f667de82c4e0c92d917c127`).

## Authority
- controller branch `phase17/ps1-title-overlay-recompile-v1`; pre-integration HEAD `36be03b5756726a20ecd69735b41cb5eba795155`
- integrated by fast-forward only

## Independent controller verification (in the P17-05R worktree)
- worktree clean at `36be03b`; 8 changed paths; zero Phase-1..16 paths
- official P17-05R gate rerun twice: run A exit 0, run B exit 0; stdout byte-identical;
  regenerated evidence byte-identical between runs **and** byte-identical to the committed evidence;
  `P17-05R_CHECKS=111`, zero non-PASS, `OPENRECOMP_P17_05R_BOUNDED_CONTINUATION=PASS`
- hardcoding audit: `0x80011af0`/derived addresses appear only in module docstrings; the continuation
  entry is derived from the recorded P17-04R `attempted_frontier_pc`, not hardcoded

## Stage result (bounded)
- cross-payload authentication: fixture member `SLUS_005.29`, file SHA-256 `c230ff5cd14bdfa392f5d5765c9c907b631875aaaa7844792b38b9ac54930f6f`,
  PS-X EXE header `t_addr=0x80010000`, `t_size=126976`, entry `0x800132e8`;
  continuation entry `0x80011af0` -> file offset `8944` (`0x22f0`)
- authentic execution advanced from the P17-04R frontier: TITLE prefix 37 instructions (last `0x80038130`),
  then 6 authenticated main-EXE instructions (`0x80011af0..0x80011b04`), frontier `0x80026cc8`
  (`PC_NOT_IN_AUTHENTICATED_TABLE`); total executed 78
- new records: main-EXE 6, TITLE 6995, total 7001, each with the full source->offset->address->word->decode->record chain

## Scope discipline
- no Phase-1..16 change; historical P17-04..P17-07 `RESULT` records untouched; all `NOT_PROVEN` markers preserved

## Remaining
- P17-06R (live BIOS/Exec + device transcript), P17-07R (GPU/OT/framebuffer frontier), P17-90 / P17-91 / P17-99
