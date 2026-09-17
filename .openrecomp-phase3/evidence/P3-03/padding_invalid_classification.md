# P3-03 — `0x04170001` classification: unreachable alignment padding or reachable invalid instructions?

VERDICT: all eight words are **unreachable non-code alignment padding**
(`code_class = PADDING_NON_CODE`, `decode_class = RESERVED_ENCODING`). They are
not reachable instructions and they are never interpreted. The P3-01
"alignment-padding" label is here independently re-derived, not inherited.

Machine record: `invalid_padding_analysis.json`, `reachable_code_map.json`,
`control_flow_frontier.json`, `instruction_inventory.json`.

## 1. Encoding analysis

`0x04170001` decomposes as:

| field | value |
|---|---|
| opcode | `0x01` (REGIMM) |
| rs | `0` |
| rt | `0x17` (23) |
| immediate | `1` |

The MIPS32 REGIMM encoding space assigns `rt` = `0x00` (`bltz`), `0x01`
(`bgez`), `0x02` (`bltzl`), `0x03` (`bgezl`), `0x08`–`0x0C` (`tgei`,
`tgeiu`, `tlti`, `tltiu`, `teqi`), `0x0E` (`tnei`), `0x10`–`0x13`
(`bltzal`, `bgezal`, `bltzall`, `bgezall`) and `0x1F` (`synci`). `rt = 0x17`
is unassigned: the word is a **reserved encoding** and is never decoded as an
instruction (`p3_decode_mips32_v1._classify_reserved`). Decoding it as any
REGIMM form would be a guess and is rejected by design.

## 2. Reachability analysis (symbol-independent)

`p3_code_frontier_v1.analyze` classifies all 3487 executable words and
discovers reachable code from the ELF entry point `0x4650` using only direct
control flow with MIPS32 delay-slot semantics. None of the eight words is
reachable (2178 words reachable; `reachable_invalid_words = 0`). Control-flow
discovery stops at each preceding function return, so no fall-through path
enters a padding run:

| run | addresses | preceding `jr $ra` | its delay slot | next function symbol |
|---|---|---|---|---|
| 1 | `0x1d8c` | `0x1d84` | `0x1d88` | `iterate` @ `0x1d90` |
| 2 | `0x25cc` | `0x25c4` | `0x25c8` | `core_bench_matrix` @ `0x25d0` |
| 3 | `0x33c8`–`0x33cc` | `0x33c0` | `0x33c4` | `get_seed_32` @ `0x33d0` |
| 4 | `0x36fc` | `0x36f4` | `0x36f8` | `uart_send_char` @ `0x3700` |
| 5 | `0x4644`–`0x464c` | `0x463c` | `0x4640` | `_start` @ `0x4650` |

The gate verifies, per run, that the preceding word is a `jr $ra` return, that
its delay slot is the following word, that the delay slot is reachable and not
a control transfer, that every padding word is `RESERVED_ENCODING` and
`UNREACHABLE`, and that no reserved encoding is reachable anywhere
(`padding:no-reachable-reserved-encoding`).

## 3. Symbol-assisted cross-check (recorded separately)

Symbols are used as a diagnostic cross-check only; reachability and decoding do
not depend on them (`symbol_assisted: true`, `symbol_usage` recorded in
`invalid_padding_analysis.json`). The 48 sized function symbols cover exactly
3479 of the 3487 executable words (disjoint union); the complement is exactly
the eight `0x04170001` words, and each run is the alignment gap between a
function's final delay slot and the next function's entry. The same statement
is asserted globally in the gate
(`padding:function-ranges-disjoint`, `padding:non-function-words-are-padding`).

## 4. Conclusion and falsifiers

The eight words are linker-emitted alignment padding between function bodies:
they are outside all function code, follow a terminating return with no
fall-through path, and carry an architecture-reserved encoding. They are
classified `PADDING_NON_CODE` + `RESERVED_ENCODING` (fail closed, never
interpreted).

The classification is falsifiable: if any direct branch/jump/call targeted one
of these addresses, or if a reachable instruction fell through into one, the
reachability engine would report a *reachable* reserved encoding, the gate
check `padding:no-reachable-reserved-encoding` would fail, and the stage would
not pass. No such path exists in the audited image.

The remaining unreachable words (`UNREACHED_CODE`, 1301) are distinct from
padding: 687 words in 22 functions never entered by direct discovery (dead
standalone copies of inlined/uncalled code) and 614 words in the unreached
parts of `core_state_transition` and `ee_printf` behind three unresolved
`jr $at` jump-table dispatch sites. Those sites are recorded in
`control_flow_frontier.json`; their targets are deliberately not invented.
