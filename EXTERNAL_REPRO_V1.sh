#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT"

fail() {
  echo "OPENRECOMP_EXTERNAL_REPRO_V1=FAIL: $*" >&2
  exit 2
}

need() {
  command -v "$1" >/dev/null 2>&1 || fail "missing required tool: $1"
}

for tool in bash git python3 clang gcc node sha256sum cmp; do
  need "$tool"
done
python3 -c 'import jsonschema' >/dev/null 2>&1 || fail "missing Python dependency: jsonschema"

if ! git diff --quiet -- || ! git diff --cached --quiet --; then
  fail "tracked working tree must be clean before the reviewer gate starts"
fi

SOURCE_HEAD="$(git rev-parse HEAD)"
[[ "$SOURCE_HEAD" =~ ^[0-9a-f]{40}$ ]] || fail "could not resolve source commit"
export OPENRECOMP_SOURCE_HEAD="$SOURCE_HEAD"

rm -rf build evidence
mkdir -p build/external-repro-v1 evidence/external-repro-v1

{
  echo "OPENRECOMP_EXTERNAL_REPRO_V1_ENVIRONMENT"
  git --version
  python3 --version
  clang --version | head -n 1
  gcc --version | head -n 1
  node --version
} > evidence/external-repro-v1/ENVIRONMENT.txt

echo "===== OPENRECOMP_EXTERNAL_REPRO_V1 ====="
echo "SOURCE_HEAD=$SOURCE_HEAD"

echo "[1/6] Hardened E07 fresh-run proof"
bash RUN.sh | tee /tmp/openrecomp-external-repro-e07.log
grep -F "PASS: E07 V1.1 HARDENED END-TO-END" /tmp/openrecomp-external-repro-e07.log >/dev/null
mkdir -p build/external-repro-v1 evidence/external-repro-v1
cp evidence/E07_RESULT.json build/external-repro-v1/e07.result.json

# RUN.sh recreates evidence/, so record environment after it completes.
{
  echo "OPENRECOMP_EXTERNAL_REPRO_V1_ENVIRONMENT"
  git --version
  python3 --version
  clang --version | head -n 1
  gcc --version | head -n 1
  node --version
} > evidence/external-repro-v1/ENVIRONMENT.txt

echo "[2/6] RV32I normalized IR/Core/Native-AOT equivalence"
python3 tools/bridge_rv32i_ir_v1.py \
  build/fixture_full.ir.json contracts/host_contract.json \
  build/external-repro-v1/rv32i.a.ir.json build/external-repro-v1/rv32i.a.sidecar.json
python3 tools/bridge_rv32i_ir_v1.py \
  build/fixture_full.ir.json contracts/host_contract.json \
  build/external-repro-v1/rv32i.b.ir.json build/external-repro-v1/rv32i.b.sidecar.json
cmp build/external-repro-v1/rv32i.a.ir.json build/external-repro-v1/rv32i.b.ir.json
cmp build/external-repro-v1/rv32i.a.sidecar.json build/external-repro-v1/rv32i.b.sidecar.json
python3 tools/validate_ir_v1.py build/external-repro-v1/rv32i.a.ir.json
python3 tools/package_ir_v1_module.py \
  build/external-repro-v1/rv32i.a.ir.json build/external-repro-v1/rv32i.a.sidecar.json \
  contracts/host_contract.json build/external-repro-v1/rv32i.a.module.json
python3 tools/package_ir_v1_module.py \
  build/external-repro-v1/rv32i.b.ir.json build/external-repro-v1/rv32i.b.sidecar.json \
  contracts/host_contract.json build/external-repro-v1/rv32i.b.module.json
cmp build/external-repro-v1/rv32i.a.module.json build/external-repro-v1/rv32i.b.module.json
python3 tools/validate_module_v1.py \
  build/external-repro-v1/rv32i.a.module.json build/external-repro-v1/rv32i.a.ir.json contracts/host_contract.json
python3 tools/run_core_api_v1.py \
  build/external-repro-v1/rv32i.a.module.json build/external-repro-v1/rv32i.a.ir.json \
  contracts/host_contract.json build/external-repro-v1/rv32i.core.json
python3 tools/aot_c_backend_v1.py \
  build/external-repro-v1/rv32i.a.module.json build/external-repro-v1/rv32i.a.ir.json \
  contracts/host_contract.json build/external-repro-v1/rv32i.a.c
python3 tools/aot_c_backend_v1.py \
  build/external-repro-v1/rv32i.a.module.json build/external-repro-v1/rv32i.a.ir.json \
  contracts/host_contract.json build/external-repro-v1/rv32i.b.c
cmp build/external-repro-v1/rv32i.a.c build/external-repro-v1/rv32i.b.c
python3 tools/native_aot_abi_v1.py \
  build/external-repro-v1/rv32i.a.module.json build/external-repro-v1/rv32i.a.ir.json \
  contracts/host_contract.json build/external-repro-v1/rv32i.abi.a.c
python3 tools/native_aot_abi_v1.py \
  build/external-repro-v1/rv32i.a.module.json build/external-repro-v1/rv32i.a.ir.json \
  contracts/host_contract.json build/external-repro-v1/rv32i.abi.b.c
cmp build/external-repro-v1/rv32i.abi.a.c build/external-repro-v1/rv32i.abi.b.c
gcc -std=c11 -O2 -Wall -Wextra -Werror -fPIC -fvisibility=hidden -shared -Iinclude \
  build/external-repro-v1/rv32i.a.c build/external-repro-v1/rv32i.abi.a.c \
  -o build/external-repro-v1/rv32i.gcc.so
clang -std=c11 -O2 -Wall -Wextra -Werror -fPIC -fvisibility=hidden -shared -Iinclude \
  build/external-repro-v1/rv32i.a.c build/external-repro-v1/rv32i.abi.a.c \
  -o build/external-repro-v1/rv32i.clang.so
python3 tools/test_native_aot_abi_v1.py \
  build/external-repro-v1/rv32i.gcc.so build/external-repro-v1/rv32i.a.module.json \
  build/external-repro-v1/rv32i.a.ir.json contracts/host_contract.json
python3 tools/test_native_aot_abi_v1.py \
  build/external-repro-v1/rv32i.clang.so build/external-repro-v1/rv32i.a.module.json \
  build/external-repro-v1/rv32i.a.ir.json contracts/host_contract.json
python3 tools/run_aot_e07_v1.py \
  build/external-repro-v1/rv32i.gcc.so contracts/host_contract.json \
  build/external-repro-v1/rv32i.aot.gcc.json
python3 tools/run_aot_e07_v1.py \
  build/external-repro-v1/rv32i.clang.so contracts/host_contract.json \
  build/external-repro-v1/rv32i.aot.clang.json
cmp build/external-repro-v1/rv32i.aot.gcc.json build/external-repro-v1/rv32i.aot.clang.json

echo "[3/6] MIPS32 vertical-slice normalized Core/Native-AOT equivalence"
python3 tools/mips32_frontend_v1.py \
  examples/mips32-v1/fixture.hex examples/mips32-v1/fixture.json contracts/host_contract.json \
  build/external-repro-v1/mips32.ir.json build/external-repro-v1/mips32.sidecar.json \
  build/external-repro-v1/mips32.frontend.json
python3 tools/validate_ir_v1.py build/external-repro-v1/mips32.ir.json
python3 tools/package_ir_v1_module.py \
  build/external-repro-v1/mips32.ir.json build/external-repro-v1/mips32.sidecar.json \
  contracts/host_contract.json build/external-repro-v1/mips32.module.json
python3 tools/validate_module_v1.py \
  build/external-repro-v1/mips32.module.json build/external-repro-v1/mips32.ir.json contracts/host_contract.json
python3 tools/run_mips32_core_v1.py \
  build/external-repro-v1/mips32.module.json build/external-repro-v1/mips32.ir.json \
  contracts/host_contract.json examples/mips32-v1/fixture.json build/external-repro-v1/mips32.core.json
python3 tools/aot_c_backend_v1.py \
  build/external-repro-v1/mips32.module.json build/external-repro-v1/mips32.ir.json \
  contracts/host_contract.json build/external-repro-v1/mips32.a.c
python3 tools/aot_c_backend_v1.py \
  build/external-repro-v1/mips32.module.json build/external-repro-v1/mips32.ir.json \
  contracts/host_contract.json build/external-repro-v1/mips32.b.c
cmp build/external-repro-v1/mips32.a.c build/external-repro-v1/mips32.b.c
python3 tools/native_aot_abi_v1.py \
  build/external-repro-v1/mips32.module.json build/external-repro-v1/mips32.ir.json \
  contracts/host_contract.json build/external-repro-v1/mips32.abi.a.c
python3 tools/native_aot_abi_v1.py \
  build/external-repro-v1/mips32.module.json build/external-repro-v1/mips32.ir.json \
  contracts/host_contract.json build/external-repro-v1/mips32.abi.b.c
cmp build/external-repro-v1/mips32.abi.a.c build/external-repro-v1/mips32.abi.b.c
gcc -std=c11 -O2 -Wall -Wextra -Werror -fPIC -fvisibility=hidden -shared -Iinclude \
  build/external-repro-v1/mips32.a.c build/external-repro-v1/mips32.abi.a.c \
  -o build/external-repro-v1/mips32.gcc.so
clang -std=c11 -O2 -Wall -Wextra -Werror -fPIC -fvisibility=hidden -shared -Iinclude \
  build/external-repro-v1/mips32.a.c build/external-repro-v1/mips32.abi.a.c \
  -o build/external-repro-v1/mips32.clang.so
python3 tools/test_native_aot_abi_v1.py \
  build/external-repro-v1/mips32.gcc.so build/external-repro-v1/mips32.module.json \
  build/external-repro-v1/mips32.ir.json contracts/host_contract.json
python3 tools/test_native_aot_abi_v1.py \
  build/external-repro-v1/mips32.clang.so build/external-repro-v1/mips32.module.json \
  build/external-repro-v1/mips32.ir.json contracts/host_contract.json
python3 tools/run_aot_mips32_v1.py \
  build/external-repro-v1/mips32.gcc.so build/external-repro-v1/mips32.ir.json \
  examples/mips32-v1/fixture.json build/external-repro-v1/mips32.aot.gcc.json
python3 tools/run_aot_mips32_v1.py \
  build/external-repro-v1/mips32.clang.so build/external-repro-v1/mips32.ir.json \
  examples/mips32-v1/fixture.json build/external-repro-v1/mips32.aot.clang.json
cmp build/external-repro-v1/mips32.aot.gcc.json build/external-repro-v1/mips32.aot.clang.json
python3 tools/check_aot_ir_v1.py \
  build/external-repro-v1/rv32i.core.json build/external-repro-v1/rv32i.aot.gcc.json \
  build/external-repro-v1/mips32.core.json build/external-repro-v1/mips32.aot.gcc.json \
  | tee evidence/external-repro-v1/dual-arch-aot.txt
grep -F "OPENRECOMP_IR_V1_AOT_DUAL_ARCH=PASS" evidence/external-repro-v1/dual-arch-aot.txt >/dev/null

echo "[4/6] MIPS32 Expansion V1 five-fixture reviewer matrix"
python3 tools/test_mips32_expansion_v1.py
fixtures=(logic-shift memory-width branches-calls mult-hilo big-endian-memory)
for name in "${fixtures[@]}"; do
  root="build/external-repro-v1/${name}"
  hex="examples/mips32-expansion-v1/${name}.hex"
  meta="examples/mips32-expansion-v1/${name}.json"

  python3 tools/mips32_expansion_frontend_v1.py "$hex" "$meta" contracts/host_contract.json \
    "${root}.a.ir.json" "${root}.a.sidecar.json" "${root}.frontend.json"
  python3 tools/mips32_expansion_frontend_v1.py "$hex" "$meta" contracts/host_contract.json \
    "${root}.b.ir.json" "${root}.b.sidecar.json" "${root}.frontend.b.json"
  cmp "${root}.a.ir.json" "${root}.b.ir.json"
  cmp "${root}.a.sidecar.json" "${root}.b.sidecar.json"
  cmp "${root}.frontend.json" "${root}.frontend.b.json"
  python3 tools/validate_ir_v1.py "${root}.a.ir.json"

  python3 tools/run_mips32_expansion_reference.py "$hex" "$meta" "${root}.reference.json"
  python3 tools/package_ir_v1_module.py \
    "${root}.a.ir.json" "${root}.a.sidecar.json" contracts/host_contract.json "${root}.a.module.json"
  python3 tools/package_ir_v1_module.py \
    "${root}.b.ir.json" "${root}.b.sidecar.json" contracts/host_contract.json "${root}.b.module.json"
  cmp "${root}.a.module.json" "${root}.b.module.json"
  python3 tools/validate_module_v1.py "${root}.a.module.json" "${root}.a.ir.json" contracts/host_contract.json
  python3 tools/run_mips32_expansion_core_v1.py \
    "${root}.a.module.json" "${root}.a.ir.json" contracts/host_contract.json "$meta" "${root}.core.json"

  python3 tools/aot_c_backend_v1.py \
    "${root}.a.module.json" "${root}.a.ir.json" contracts/host_contract.json "${root}.a.c"
  python3 tools/aot_c_backend_v1.py \
    "${root}.a.module.json" "${root}.a.ir.json" contracts/host_contract.json "${root}.b.c"
  cmp "${root}.a.c" "${root}.b.c"
  python3 tools/native_aot_abi_v1.py \
    "${root}.a.module.json" "${root}.a.ir.json" contracts/host_contract.json "${root}.abi.a.c"
  python3 tools/native_aot_abi_v1.py \
    "${root}.a.module.json" "${root}.a.ir.json" contracts/host_contract.json "${root}.abi.b.c"
  cmp "${root}.abi.a.c" "${root}.abi.b.c"

  gcc -std=c11 -O2 -Wall -Wextra -Werror -fPIC -fvisibility=hidden -Iinclude -shared \
    "${root}.a.c" "${root}.abi.a.c" -o "${root}.gcc.so"
  clang -std=c11 -O2 -Wall -Wextra -Werror -fPIC -fvisibility=hidden -Iinclude -shared \
    "${root}.a.c" "${root}.abi.a.c" -o "${root}.clang.so"
  python3 tools/test_native_aot_abi_v1.py \
    "${root}.gcc.so" "${root}.a.module.json" "${root}.a.ir.json" contracts/host_contract.json
  python3 tools/test_native_aot_abi_v1.py \
    "${root}.clang.so" "${root}.a.module.json" "${root}.a.ir.json" contracts/host_contract.json
  python3 tools/run_aot_mips32_expansion_v1.py \
    "${root}.gcc.so" "${root}.a.ir.json" "$meta" "${root}.aot.gcc.json"
  python3 tools/run_aot_mips32_expansion_v1.py \
    "${root}.clang.so" "${root}.a.ir.json" "$meta" "${root}.aot.clang.json"
  python3 tools/check_mips32_expansion_v1.py \
    "$meta" "${root}.frontend.json" "${root}.a.ir.json" "${root}.a.module.json" \
    "${root}.reference.json" "${root}.core.json" "${root}.aot.gcc.json" "${root}.aot.clang.json" \
    | tee "evidence/external-repro-v1/${name}.txt"
done

echo "[5/6] Restore tracked evidence and run public safety"
# RUN.sh intentionally recreates evidence/. Restore only tracked evidence from the reviewed commit;
# untracked external-repro-v1 evidence remains in place for verification and upload.
git restore --source=HEAD --worktree -- evidence
python3 tools/public_safety_scan.py | tee evidence/external-repro-v1/public-safety.txt
grep -F "OPENRECOMP_PUBLIC_SAFETY=PASS" evidence/external-repro-v1/public-safety.txt >/dev/null
if ! git diff --quiet -- || ! git diff --cached --quiet --; then
  git diff --summary >&2 || true
  git diff --name-status >&2 || true
  fail "reviewer gate modified tracked repository content"
fi

echo "[6/6] Write and verify deterministic machine-readable result"
python3 tools/write_external_repro_v1_result.py
python3 tools/verify_external_repro_v1.py

echo "OPENRECOMP_EXTERNAL_REPRO_V1_SOURCE_HEAD=$SOURCE_HEAD"
echo "OPENRECOMP_EXTERNAL_REPRO_V1=PASS"
echo "Evidence: $ROOT/evidence/external-repro-v1/RESULT.json"
