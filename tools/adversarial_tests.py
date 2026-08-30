#!/usr/bin/env python3
import json,struct,subprocess,sys,tempfile
from pathlib import Path
R=Path(__file__).resolve().parents[1]
def check(name,cmd,prefix):
 p=subprocess.run(cmd,cwd=R,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 tail=p.stderr[p.stderr.find(prefix):] if prefix in p.stderr else p.stderr
 if p.returncode!=2 or prefix not in p.stderr or 'Traceback' in tail: raise SystemExit(f'FAIL {name}: rc={p.returncode} {p.stderr}')
 print('PASS',name)
with tempfile.TemporaryDirectory() as td:
 td=Path(td); b=bytearray((R/'build/fixture_full.elf').read_bytes())
 shoff=struct.unpack_from('<I',b,32)[0]; ents=struct.unpack_from('<H',b,46)[0]; n=struct.unpack_from('<H',b,48)[0]; si=struct.unpack_from('<H',b,50)[0]
 hs=[struct.unpack_from('<IIIIIIIIII',b,shoff+i*ents) for i in range(n)]; st=hs[si]; names=bytes(b[st[4]:st[4]+st[5]])
 ti=None
 for i,h in enumerate(hs):
  no=h[0]; e=names.find(b'\0',no)
  if names[no:e]==b'.text': ti=i; break
 h=hs[ti]; x=bytearray(b); o=shoff+ti*ents; struct.pack_into('<I',x,o+4,8); struct.pack_into('<I',x,o+16,len(x)+4096)
 f=td/'nobits.elf'; f.write_bytes(x); check('text_nobits',['python3','tools/elf_loader.py',str(f)],'ELF_REJECT:')
 x=bytearray(b); x[h[4]:h[4]+4]=b'\0\0\0\0'; f=td/'badop.elf'; f.write_bytes(x); check('bad_opcode',['python3','tools/make_ir.py',str(f),str(td/'i'),str(td/'m')],'IR_REJECT:')
 ir=json.loads((R/'build/fixture_full.ir.json').read_text()); ir['ir_version']='999'; f=td/'badir.json'; f.write_text(json.dumps(ir)); check('bad_schema',['python3','tools/translate.py',str(f),str(td/'x.c')],'TRANSLATE_REJECT:')
 ir=json.loads((R/'build/fixture_full.ir.json').read_text()); ir['symbols']=[s for s in ir['symbols'] if s['name']!='host_system']; f=td/'badhost.json'; f.write_text(json.dumps(ir)); check('missing_host',['python3','tools/translate.py',str(f),str(td/'x.c')],'TRANSLATE_REJECT:')
print('PASS adversarial corpus')
