# P11-07 — B0:57 public contract and bounded first-frame blocker

`PASS` — rigorously bounded with
`BLOCKED_BY_SPECIFIC_MISSING_EVIDENCE`.

The official gate `tools/test_phase11_b0_table_v1.py` passed 41 checks twice
through the Phase-11 stage runner. Both runs exited 0, produced empty stderr,
and had byte-identical stdout and JSON sidecars. The unchanged P11-06 and
P11-05 dependency gates also passed twice at 75 and 294 checks respectively.

## Public contract

The pinned public sources establish only this B0:57 contract:

- vector/index: `B0:0x57`;
- name: `GetB0Table`;
- arguments: none;
- result: guest pointer returned in `$v0`;
- object: mutable, word-indexed B0 BIOS jump table;
- no GPU, renderer, DMA, VRAM, interrupt, timing or frame behavior.

The source record pins PSX-SPX revision
`f37fc9a7a889a55e3bdec2d09a8a34640edf3082`, PCSX-Redux revision
`911271b7af5008a2fbbcb9b2390e26475208423d` with its OpenBIOS/nugget
submodule at `77adff516017044f2c6d9b21f66c124b9593959a` under the MIT license,
and the independently structured GPL-2.0 PCSX HLE implementation at
`7787631c6ee37a489732c95cb0864422e3a3bdd1`.

PCSX HLE returns `0x00000874`, while current OpenBIOS returns its own
linker-assigned `B0table` object. This corroborates the API but proves that a
fixed table address is not part of the portable contract. OpenBIOS also
establishes a mutable 0x60-entry pointer array and explicit unimplemented
thunks, but its entries point into OpenBIOS code that is not present in the
OpenRecomp runtime.

## Exact caller use

The private caller remains bounded to non-reconstructive neutral-IR metadata.
After the B0:57 return it:

1. performs an aligned 32-bit read at table offset `0x16C`, entry `0x5B`;
2. treats that entry as the `ChangeClearPAD` function pointer;
3. stores pointers derived at offsets `0x884` and `0x894`;
4. clears eleven aligned 32-bit words at target-relative offsets
   `0x594` through `0x5BC`;
5. continues to an already translated direct call only after those mutations.

PSX-SPX independently documents this patch pattern. The caller therefore
does not merely retain the table pointer and does not patch the table entry;
it depends on the entry's guest function pointer and a writable internal
function-relative layout.

## Bounded decision

No legal B variant can presently be constructed. The public sources do not
provide a portable guest address/callable representation for B0:0x5B, a guest
code/data object that makes those relative writes valid without loading or
executing a BIOS, or a non-fabricated fail-closed target representation for
the other readable entries. Returning `0x00000874` with an empty table,
inventing an entry pointer, or copying a retail/OpenBIOS code layout would
violate the stage contract.

Accordingly:

- B0:57 is now named in the existing BIOS index classification only;
- it remains `BIOS_VECTOR_NOT_IMPLEMENTED` / `FAIL_CLOSED`;
- no runtime service, dispatcher branch, guest table, indirect target, GPU or
  device behavior was added;
- the causal A boundary remains `0x80015FA4`, block index `468341`;
- there is no evidence-valid next dynamic frontier;
- milestone D and all later playability milestones remain `NOT_PROVEN`.

P11-08 is not started because Phase 11 is serial and the exact P11-07 frontier
has not advanced.
