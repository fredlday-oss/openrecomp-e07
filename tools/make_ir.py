#!/usr/bin/env python3
import json, sys
import jsonschema
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.elf_loader import load_elf, public, ELFError
from adapters import riscv32

HOST={'host_graphics','host_audio','host_input','host_system'}

def validate_ir(ir):
    schema=json.loads((Path(__file__).resolve().parents[1]/'schema'/'ir.schema.json').read_text())
    jsonschema.validate(ir,schema)

def build(path):
    m=load_elf(path); b=m['_bytes']; text=m['_text']; start=text['addr']; end=start+text['size']
    ins=[]
    for a in range(start,end,4):
        off=text['offset']+(a-start); word=int.from_bytes(b[off:off+4],'little')
        try: d=riscv32.decode(a,word)
        except ValueError as e: raise ValueError(f'decode rejected: {e}') from None
        ins.append(d)
    sym_by_addr={s['value']:s for s in m['symbols'] if s['type']==2 and s['value']}
    funcs=[]; direct_call_graph=[]; unresolved_indirect_calls=[]; targets={start}
    for d in ins:
        if d['op'] in ('bltu','bgeu','beq','bne','jal'): targets.add(d.get('target',0))
        if d['op'] in ('bltu','bgeu','beq','bne'): targets.add(d['address']+4)
        if d['op']=='jal' and d['rd']==1:
            src=None
            for s in m['symbols']:
                if s['type']==2 and s['value']<=d['address']<s['value']+max(s['size'],4): src=s['name']; break
            dst=sym_by_addr.get(d['target'],{}).get('name',f"0x{d['target']:x}")
            direct_call_graph.append({'from':src or '<unknown>','to':dst,'site':d['address'],'host_stub':dst in HOST})
    for d in ins:
        if d['op']=='jalr': unresolved_indirect_calls.append({'site':d['address'],'kind':'jalr','rd':d['rd'],'rs1':d['rs1'],'imm':d['imm']})
        elif d['op']=='jal' and d['rd']==0: unresolved_indirect_calls.append({'site':d['address'],'kind':'tail-jal','target':d['target']})
    for s in sorted((x for x in m['symbols'] if x['type']==2 and x['size'] and start<=x['value']<end),key=lambda x:x['value']):
        fi=[d for d in ins if s['value']<=d['address']<s['value']+s['size']]
        starts=sorted({s['value']}|{t for t in targets if s['value']<=t<s['value']+s['size']})
        blocks=[]
        for idx,bs in enumerate(starts):
            be=starts[idx+1] if idx+1<len(starts) else s['value']+s['size']
            block_ins=[d['address'] for d in fi if bs<=d['address']<be]
            if block_ins: blocks.append({'start':bs,'instruction_addresses':block_ins})
        funcs.append({'name':s['name'],'address':s['value'],'size':s['size'],'basic_blocks':blocks})
    markers=[c for c in direct_call_graph if c['host_stub']]
    ir={
      'ir_version':'0.1.1','architecture':riscv32.info.architecture_id,'architecture_adapter':{
        'bits':riscv32.info.bits,'endianness':riscv32.info.endianness,'registers':list(riscv32.info.registers),'calling_convention':riscv32.info.calling_convention},
      'input_sha256':m['input_sha256'],'entry_point':m['entry_point'],'fixture_entry':next(s['value'] for s in m['symbols'] if s['name']=='fixture_main'),
      'functions':funcs,'basic_block_count':sum(len(f['basic_blocks']) for f in funcs),'direct_call_graph':direct_call_graph,'unresolved_indirect_calls':unresolved_indirect_calls,'host_markers':markers,
      'instructions':ins,'alloc_sections':m['alloc_sections'],'symbols':m['symbols']
    }
    validate_ir(ir)
    return ir, public(m)

if __name__=='__main__':
    try:
        ir,meta=build(sys.argv[1]); Path(sys.argv[2]).write_text(json.dumps(ir,indent=2,sort_keys=True)+'\n'); Path(sys.argv[3]).write_text(json.dumps(meta,indent=2,sort_keys=True)+'\n')
    except (ELFError,ValueError,KeyError,StopIteration,jsonschema.ValidationError) as e:
        print(f'IR_REJECT: {e}',file=sys.stderr); raise SystemExit(2)
