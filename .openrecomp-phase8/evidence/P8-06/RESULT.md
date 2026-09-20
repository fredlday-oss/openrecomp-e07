# P8-06 result: host-source emission

Status: `PASS` (25 checks)

Markers:

- `OPENRECOMP_P8_06=PASS`
- `OPENRECOMP_PHASE8_HOST_EMISSION_V1=PASS tests=25`
- `OPENRECOMP_PHASE8_MIPS32_END_TO_END_NATIVE_PROOF=NOT_PROVEN` (reserved)
- `OPENRECOMP_PHASE8_GENERAL_MIPS32_COMPATIBILITY=NOT_PROVEN` (permanent)

Gate: `python tools/test_phase8_emission_v1.py`.

## Deterministic build input set

`.openrecomp-phase8/src/p8_emission_v1.py` composes the complete emission set
with stable filenames and recorded content hashes:

| File | Bytes | SHA-256 |
|---|---|---|
| `program.c` | 97830 | `3df423e0efdd1b6d0c91ce9f95bd33d0b58f08833226314bd43aff407751c704` |
| `p8_image_v1.c` | 166198 | `d5d95845cf6574b7791996bdacd4d1f6994359c9e6c6911e71f1e006fb9b6d8d` |
| `p8_runtime_support.c` | 7662 | `9b5e70f524741612fc25a2def189fe436c757ceb4e064daa3c4f76088b9595c5` |
| `p8_driver.c` | 4172 | `e918de647ed34d9eaf451b93beb6b4f490676484c737484b7d8602f500f2ecea` |

`program.c` is byte-identical to the P8-04 emission (fingerprint
`3df423e0...`; the file hash equals the fingerprint because the source is
ASCII), and two independent emissions in the gate are byte-identical. The
only revision since the first record is the P8-04 `movz` ISA correction; the
emission-set digest is now `e66fa2399334f28188192fb5a3826eff2748909f3d3d9fa2af31a4781584e71f`. The
program declares 7 per-function host translations (`fn_fn_1000`, `fn_fn_101c`,
`fn_fn_11b8`, `fn_fn_11dc`, `fn_fn_2290`, `fn_fn_2360`, `fn_fn_2490`), the
`openrecomp_run` driver boundary and 463 emitted neutral operations; it has no
`main` (the observable driver supplies it), no image reference, no inline
assembly and no embedded instruction array.

## No original machine code at runtime

`p8_image_v1.c` embeds the guest bytes only as inert `const unsigned char`
data (the file begins with the ELF magic as array data) with no control flow;
`program.c` contains only generated C semantics over the register file and the
generic runtime ABI. The runtime never executes a guest address directly.

## Observable record (agreed here, consumed at P8-07/P8-08/P8-09)

`p8_driver.c` prints a bounded record: fixture SHA-256, `failed`, `error`,
`exit_status` (`$v0`), all 32 guest registers at the return boundary, an
FNV-1a 64 digest of the register file, an FNV-1a 64 digest of the full guest
image, output transcript length and digest, and read/write/host-call/denied
counters. The digest recipe (offset basis `0xcbf29ce484222325`, prime
`0x100000001b3`) is stated in the driver source for the independent reference.

## Official runs

Command `python tools/test_phase8_emission_v1.py`, exit 0, empty stderr, both
runs byte-identical: stdout 913 bytes, raw sha256
`f2e884a3020f66ddbc66c7dee252ae54d4d906fea3af7390956483ab1b1a4647`, LF
sha256 `998042ec3f38efdd5a0eff93d446313655736e96cc6242cc544f7126b9b44697`.

Sidecar identities (post-correction): `emission_set.json`
`0cdc1721f44d4dbc62be3c282396c055f462b4ab4672c678cf311292449c368e`,
`p8_06_tests.json`
`a62bd48c76a43d23e14de927fe5effc6b23da8a3089f49a0e18d5d1fba6fa8bc`.

## Claim-ledger delta

- New evidence: the frozen real program now has a complete, deterministic,
  content-addressed host-source build set ready for native compilation.
- Nothing has been compiled or executed; the terminal marker remains reserved
  `NOT_PROVEN`.

## Limitations

- The emission covers exactly the frozen fixture structure and the closed
  rule table; it is not general MIPS32 emission.
- `p8_image_v1.c` embeds the fixture's load image as required initialized
  data; no other binary material is embedded.

## Next stage

P8-07: compile the emission set through the existing host-native
toolchain/runtime boundary, recording incremental development build reuse and
one clean audited build path.
