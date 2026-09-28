# P18-04 Recovery Addendum (controller)

Recovered during Phase-18 autonomous continuation after the previous session
failed mid-flight. No reset, clean, or overwrite was performed; the inherited
working-tree change was preserved and independently validated.

## Live Git authority at recovery

- branch: `phase18/ps1-first-frame-frontier-v1`
- HEAD at recovery start: `21ce4cbb506b08f9635c635b2dbe9778d94656af` (tree `7fafddddc4470aeb94e91bd8e8f579d853ac5a12`)
- P18-06 committed (PASS); P18-07 contract authored but uncommitted.

## Defect found (D8, inherited, uncommitted, half-applied)

`build_gpu_command_frontier()` and `frontier_bytes()` in
`.openrecomp-phase18/src/p18_gpu_command_frontier_v1.py` appended the
**two-character literal** token `"\n"` (backslash + n) instead of a newline.
The resulting `gpu_command_frontier.json` therefore carried its JSON
pretty-print plus a trailing `\n` sequence, so the artifact was **not valid
JSON**.

- Committed artifact digest `297a549350e89c4fdf765353c7cf6ff9a1f9a0e563c8c62b02a33677943be58b`
  -> `json.load` raises `JSONDecodeError: Extra data: line 27 column 2`.
- All other Phase-18 producers (P18-02/P18-03/P18-05/P18-06 modules, the gate
  helper, the P17 tree) correctly use a real `"\n"` newline; P18-04 was the
  sole outlier.

An incomplete repair was present in the working tree: the source lines were
corrected and the gate re-run once, which regenerated only some artifacts and
left `official_runs.json`, `determinism.json` and the run logs stale and
inconsistent with the new digest.

## Independent validation of the inherited direction

The correction is the faithful behaviour, not the defect: the module's own
returned digest must equal the bytes it returns via `frontier_bytes()`, and
the gate writes exactly those bytes to `gpu_command_frontier.json`. The
committed literal-token form can never satisfy that self-consistency, and it
emits an artifact no Phase-18 consumer can parse. The repair was therefore
completed rather than reverted, with no assertion weakened and no tolerance
widened.

## Repair performed

- Regenerated P18-04 evidence with the corrected producer under the
  authoritative stage runner (dual official runs).
- Result: `runner_status=PASS`, exit 0, empty stderr both runs, raw and
  LF-normalized stdout byte-identical, all evidence artifacts byte-identical
  across both runs.
- `gpu_command_frontier.json` is now valid JSON with digest
  `a009003b644122a011a4a53a9ceeae1d2e4a560a462fc28ef2c3ac9dd4b2bfe9`;
  `gpu_command_frontier.sha256`, `RESULT.json`, `negative_tests.json`,
  `official_runs.json` and `determinism.json` all agree on it.
- Semantic content is unchanged: GP0/GP1 frontier remains `UNREACHED`
  (`gp0_write_count=0`, `gp1_write_count=0`), `FIRST_FRAME_READY=NO`,
  all `OPENRECOMP_PHASE18_*` claim markers `NOT_PROVEN`.
- `SOURCE_SHA256SUMS.txt` regenerated from disk truth; manifest verifies
  `OPENRECOMP_PHASE18_SOURCE_INTEGRITY=PASS entries=23`.

## Consequence for downstream stages

Because the committed P18-04 frontier digest was unparsable, the committed
P18-05/P18-06 evidence inherited an unparsable input. They are re-validated in
their own gates during this recovery; their semantically-independent verdicts
(GP0/GP1, DMA and VRAM/display frontiers all `UNREACHED`) are expected to be
unaffected, but P18-07's read-and-parse precondition requires the lineage to be
coherent, which this repair restores.

## Proof boundary

Promotes no proof marker. The repair is a producer-correctness fix; it does not
establish any first-frame, initialization, playability or compatibility
property.
