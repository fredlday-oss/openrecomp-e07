#!/usr/bin/env python3
import hashlib,json,platform,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ver(cmd):
    try:return subprocess.check_output(cmd,text=True,stderr=subprocess.STDOUT).splitlines()[0]
    except:return 'unavailable'
root=Path(sys.argv[1]); out=Path(sys.argv[2])
manifest={
 'manifest_version':'0.1.0','generated_at_utc':datetime.now(timezone.utc).isoformat(),
 'input_sha256':sha(root/'build/fixture_full.elf'),'ir_sha256':sha(root/'build/fixture_full.ir.json'),
 'ir_schema_version':'0.1.1','translator_version':'0.1.1','host_contract_version':'0.1.1','generated_c_sha256':sha(root/'build/generated.c'),
 'native_binary_sha256':sha(root/'build/fixture_native'),'wasm_sha256':sha(root/'build/fixture.wasm'),
 'outputs':{x:sha(root/'build/outputs'/x) for x in ['frame.ppm','audio.wav','state.json']},
 'toolchain':{'clang':ver(['clang','--version']),'gcc':ver(['gcc','--version']),'node':ver(['node','--version']),'python':platform.python_version()},
 'compile_flags':{'input':'--target=riscv32-unknown-elf -march=rv32i -mabi=ilp32 -O0 -ffreestanding -fno-builtin -fno-stack-protector -fno-pic -nostdlib -Wl,--build-id=none', 'native':'-O2 -std=c11 -Wl,--build-id=none', 'wasm':'--target=wasm32 -O2 -nostdlib -Wl,--no-entry -Wl,--export=run_fixture'},
 'rights_statement':'Synthetic original source only; no proprietary game assets, keys, firmware, SDK material, or console-derived binary formats.'
}
out.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
