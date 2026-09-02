# Building and validating OpenRecomp E07

The current hardened E07 proof uses system-provided development tools and does not vendor third-party source dependencies.

## Required tools

- Python 3
- Python package: `jsonschema`
- LLVM/Clang with RV32I and WebAssembly target support
- `lld` / `wasm-ld`
- GCC
- Node.js
- Git
- Bash and standard utilities including `sha256sum` and `cmp`

## Hardened E07 proof

```bash
./RUN.sh
```

A successful run ends with:

```text
===== PASS: E07 V1.1 HARDENED END-TO-END =====
```

The runner verifies source integrity before generating build/evidence output.

## External reviewer path

For the broader bounded open-core reviewer gate, use a clean Linux checkout with the prerequisites above and run:

```bash
bash EXTERNAL_REPRO_V1.sh
```

A successful run ends with:

```text
OPENRECOMP_EXTERNAL_REPRO_V1=PASS
```

and writes a deterministic semantic result to `evidence/external-repro-v1/RESULT.json` plus its SHA-256 record. The gate covers the hardened E07 path, normalized RV32I/Core/AOT validation, the bounded MIPS32 vertical slice, all five MIPS32 Expansion V1 fixtures, Linux GCC/Clang Native AOT parity for the included fixtures, public-safety scanning and tracked-tree immutability.

The reference hosted environment is Ubuntu 24.04, Python 3.12, Node.js 22 and `jsonschema` 4.26.0. System compiler patch versions are diagnostic provenance rather than part of the deterministic semantic result.

See [`EXTERNAL_REPRO_V1.md`](EXTERNAL_REPRO_V1.md) for the exact scope and exclusions, and [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md) for the wider checksum/evidence model.
