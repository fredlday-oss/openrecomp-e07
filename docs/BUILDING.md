# Building and validating OpenRecomp E07

The current hardened E07 proof uses system-provided development tools and does not vendor third-party source dependencies.

## Required tools

- Python 3
- Python package: `jsonschema`
- LLVM/Clang with RV32I and WebAssembly target support
- `lld` / `wasm-ld`
- GCC
- Node.js
- Bash and standard utilities including `sha256sum` and `cmp`

## Run

```bash
./RUN.sh
```

A successful run ends with:

```text
===== PASS: E07 V1.1 HARDENED END-TO-END =====
```

The runner verifies source integrity before generating build/evidence output.

See [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md) for the checksum and evidence model.
