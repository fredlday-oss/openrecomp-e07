# OpenRecomp E07 dependencies and licence inventory

This inventory covers the current public E07 synthetic fixture and its `RUN.sh` pipeline. No third-party source is vendored into this repository.

## Runtime / build dependencies

| Dependency | Role | Licence / status | Redistributed here? |
| --- | --- | --- | --- |
| Python 3 | Loader, IR generation, validation, provenance and adversarial tests | PSF License | No |
| `jsonschema` Python package | Machine-enforced IR schema validation | MIT | No |
| LLVM/Clang | RV32I fixture build and WebAssembly build | Apache-2.0 WITH LLVM-exception | No |
| GCC | Native x86-64 host build | GPLv3 with GCC Runtime Library Exception for relevant runtime components | No |
| Node.js | Executes the generated WebAssembly fixture | MIT for Node.js core; bundled third-party components retain their own licences | No |
| POSIX shell/core utilities (`bash`, `sha256sum`, `cmp`) | Pipeline orchestration and deterministic comparisons | System-provided tools; not redistributed | No |

## Python standard-library modules used

`hashlib`, `json`, `pathlib`, `dataclasses`, `datetime`, `typing`, and other standard-library facilities are supplied with Python and are not vendored.

## JavaScript dependencies

`tools/wasm_run.js` uses Node's built-in `fs` module only. There is no npm dependency and no `package.json` in E07 V1.1.

## Repository-owned material

The OpenRecomp E07 source, schema, contracts, synthetic corpus, linker script, test harnesses and reviewed golden fixtures are project-owned/original material. The project intends to distribute these under Apache License 2.0 once the repository `LICENSE` file is added.

## Rights firewall

The repository contains no commercial game binaries or assets, console keys, firmware, proprietary SDK material, or console-specific executable format samples.

## NLnet relevance

This inventory is intended to make the dependency and licensing boundary explicit for the NLnet Restack application. Any new dependency introduced during grant-funded work should be added here before release and checked for compatibility with the project's intended Apache-2.0 distribution terms.
