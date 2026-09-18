# P4-08 result (PASS)

Stage: `OPENRECOMP_PHASE4_ADAPTER_EXECUTION_V1`. Evidence:
`.openrecomp-phase4/evidence/P4-08/`. Gate:
`tools/test_phase4_adapter_execution_v1.py` (73 checks, sha256
`7a2424747ee212542dd7123445040acbbb3fbd96f287c59512d4abda5349c4e0`).

Markers issued:

- Stage marker: `OPENRECOMP_P4_08=PASS`
- Gate marker: `OPENRECOMP_PHASE4_ADAPTER_EXECUTION_V1=PASS tests=73`
- Terminal marker (reserved): `OPENRECOMP_PHASE4_GENERIC_RUNTIME_PROOF=NOT_PROVEN`
- General compatibility marker (never promoted):
  `OPENRECOMP_PHASE4_GENERAL_COMPATIBILITY=NOT_PROVEN`

Delivered (additive Phase-4 files only; frozen modules used read-only):

- `.openrecomp-phase4/src/p4_fixture_exec_v1.py`: fixture rebuild/pinned
  identity, region/image extraction, frozen decode-frontier analysis,
  architecture-neutral emission of every reachable word through the frozen
  instruction emitter, the declared fixture instance profile
  (`fixture.exit`=1, `fixture.in`=2, `fixture.out`=3, `fixture.ticks`=4) and
  the runtime support implementing checked memory, typed service dispatch,
  the deterministic input plan, bounded output, virtual ticks and the P4-01
  canonical observable.
- `tools/test_phase4_adapter_execution_v1.py`; Phase-4 manifest grown
  additively to 25 entries.

Verified: 774 reachable words emitted; reserved padding not emitted;
unsupported records fail closed at emission; generated program/support pass
the P4-01 ABI verifier against the fixture profile; deterministic
`EXECUTABLE_REPRODUCIBLE` build (program `abd138ea...`, support
`755a004630...`, executable `c966e185...`); three identical native replays
producing the exact P4-07-model transcript (`input_bytes=4`, `input_xor=136`,
`fib10=55`, `prime_count=16`, `primes_sum=381`, `bss_sum=4028012831`,
`heap_sum=3784880468`, `checksum=0xd43e5ba6`), pinned tick fields
(`ticks_start=19`, `ticks_end=6691`), `steps=6784`, `pc=0x1bf4`,
`state_fnv1a64=0x5185479717fe4020`, no failure; the `BoundPlatform` fixture
adapter (memory map, generic service aliases, recorded input, boundary hooks)
exposes the same declared service profile and mediates fail-closed
(post-exit and unknown services); tiny negative programs fail closed on an
unmapped store and on step-limit exhaustion.

Two official runs byte-identical raw (1779 bytes `4449d842...`, empty
stderr, exit 0) with `p4_08_tests.json` identical across runs.

Regressions: P2-08 `PASS tests=169`, P4-01..P4-07 all PASS, Phase-1 host
gates `PASS=44 FAIL=0 SKIPPED=2`, public safety `PASS`, P4-00
`PASS tests=74` (`953312d0...`) with the documented dynamic boundary-context
hygiene.

Limitations: the proof is bounded to the audited fixture and profile; the
native support is the concrete adapter/runtime implementation for this
fixture (not a universal runtime); tick values depend on the declared
one-tick-per-retired-instruction policy; independent-reference equivalence is
P4-09 scope; `GENERIC_RUNTIME_STATUS=NOT_PROVEN`.
