#!/usr/bin/env python3
'''Phase 5/6 equivalence gate: oracle result must match native compiled result.

Uses artifacts/mips32_translation_v1/TRANSLATION_FIXTURE.elf as the
canonical fixture.  Writes evidence to:
  artifacts/mips32_translation_evidence_closure_v1/oracle/ORACLE_RESULT.json
  artifacts/mips32_translation_evidence_closure_v1/native/NATIVE_RESULT.json
  artifacts/mips32_translation_evidence_closure_v1/EQUIVALENCE_RESULT.json

Exits 0 on EQUIVALENCE_PASS, 1 on failure.
'''
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

_TOOLS = Path(__file__).resolve().parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from mips32_oracle_v1 import simulate

_ROOT = _TOOLS.parent
_ELF = _ROOT / 'artifacts' / 'mips32_translation_v1' / 'TRANSLATION_FIXTURE.elf'
_CONTRACT = _ROOT / 'contracts' / 'host_contract.json'
_HARNESS = _ROOT / 'scratch' / 'harness.c'
_CLOSURE = _ROOT / 'artifacts' / 'mips32_translation_evidence_closure_v1'


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_harness_output(output: str) -> tuple:
    '''Parse r2=N r3=M from harness exe output.

    harness.c printf uses a literal backslash-n so the exe emits
    r2=N r3=M followed by backslash-n (two chars), not a real newline.
    '''
    line = output.strip().replace('\\n', '')
    parts = line.split()
    r2 = int(parts[0].split('=')[1])
    r3 = int(parts[1].split('=')[1])
    return r2, r3


def main() -> int:
    if not _ELF.exists():
        from build_mips32_translation_fixture import build
        build(_ELF)

    oracle = simulate(str(_ELF))
    elf_sha = _sha256(_ELF)

    (_CLOSURE / 'oracle').mkdir(parents=True, exist_ok=True)
    oracle_result = {
        'fixture_sha256': elf_sha,
        'entry_pc': '0x1000',
        'instruction_count': oracle['operations'],
        'r0': 0,
        'r2': oracle['r2'],
        'r3': oracle['r3'],
        'observable_result': oracle['r2'],
        'termination_reason': 'jr_ra_to_zero',
    }
    (_CLOSURE / 'oracle' / 'ORACLE_RESULT.json').write_text(
        json.dumps(oracle_result, indent=2), encoding='utf-8'
    )
    print(f"Oracle: r2={oracle['r2']} r3={oracle['r3']} ops={oracle['operations']}")

    eq_dir = _CLOSURE / 'equivalence'
    eq_dir.mkdir(parents=True, exist_ok=True)

    ir_path = eq_dir / 'ir.json'
    sidecar_path = eq_dir / 'sidecar.json'
    module_path = eq_dir / 'module.json'
    out_c = eq_dir / 'generated.c'
    exe = eq_dir / 'host_execution.exe'

    def run(*args):
        r = subprocess.run([sys.executable, *args], capture_output=False)
        if r.returncode != 0:
            raise RuntimeError(f'{args[0]} exited {r.returncode}')

    run(_TOOLS / 'translate_mips32_elf_v1.py', _ELF, _CONTRACT, ir_path, sidecar_path)
    run(_TOOLS / 'package_ir_v1_module.py', ir_path, sidecar_path, _CONTRACT, module_path)
    run(_TOOLS / 'aot_c_backend_v1.py', module_path, ir_path, _CONTRACT, out_c)

    import shutil
    harness_dst = eq_dir / 'harness.c'
    shutil.copyfile(_HARNESS, harness_dst)

    build_script = eq_dir / '_build.py'
    build_script.write_text(
        'import sys, distutils.sysconfig\n'
        'from setuptools._distutils.ccompiler import new_compiler\n'
        'compiler = new_compiler()\n'
        'distutils.sysconfig.customize_compiler(compiler)\n'
        'try:\n'
        '    objs = compiler.compile(["generated.c", "harness.c"], output_dir=".")\n'
        '    compiler.link_executable(objs, "host_execution", output_dir=".")\n'
        'except Exception as exc:\n'
        '    print(exc)\n'
        '    sys.exit(1)\n',
        encoding='utf-8',
    )
    r = subprocess.run([sys.executable, str(build_script)], cwd=str(eq_dir))
    if r.returncode != 0:
        print('FAIL: compilation failed', file=sys.stderr)
        return 1

    res = subprocess.run([str(exe)], capture_output=True, text=True)
    if res.returncode != 0:
        print(f'FAIL: execution returned {res.returncode}: {res.stderr}', file=sys.stderr)
        return 1

    native_r2, native_r3 = _parse_harness_output(res.stdout)
    print(f'Native: r2={native_r2} r3={native_r3}')

    exe_sha = _sha256(exe)
    c_sha = _sha256(out_c)

    (_CLOSURE / 'native').mkdir(parents=True, exist_ok=True)
    (_CLOSURE / 'native' / 'NATIVE_RESULT.json').write_text(
        json.dumps({
            'executable_sha256': exe_sha,
            'generated_c_sha256': c_sha,
            'r0': 0,
            'r2': native_r2,
            'r3': native_r3,
            'observable_result': native_r2,
            'exit_code': 0,
        }, indent=2),
        encoding='utf-8',
    )
    (_CLOSURE / 'native' / 'NATIVE_EXECUTION.txt').write_text(res.stdout, encoding='utf-8')

    differences = []
    if oracle['r2'] != native_r2:
        differences.append(f"r2: oracle={oracle['r2']} native={native_r2}")
    if oracle['r3'] != native_r3:
        differences.append(f"r3: oracle={oracle['r3']} native={native_r3}")

    verdict = 'EQUIVALENCE_PASS' if not differences else 'EQUIVALENCE_FAIL'
    eq_result = {
        'oracle_fixture_sha256': elf_sha,
        'native_fixture_sha256': elf_sha,
        'oracle_state': {'r2': oracle['r2'], 'r3': oracle['r3']},
        'native_state': {'r2': native_r2, 'r3': native_r3},
        'differences': differences,
        'verdict': verdict,
    }
    (_CLOSURE / 'EQUIVALENCE_RESULT.json').write_text(
        json.dumps(eq_result, indent=2), encoding='utf-8'
    )
    print(verdict)
    return 0 if verdict == 'EQUIVALENCE_PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
