#!/usr/bin/env python3
"""P17-06 bounded authentic execution from authenticated decoded records."""
from __future__ import annotations
import hashlib,json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]
DECODE=ROOT/'.openrecomp-phase17/evidence/P17-02/title_decode.json'; ENTRY=0x800380A0
class ExecutionError(ValueError): pass
def _digest(d,key): return hashlib.sha256(json.dumps({k:v for k,v in d.items() if k!=key},sort_keys=True).encode()).hexdigest()
def _load():
 try: d=json.loads(DECODE.read_text())
 except (OSError,json.JSONDecodeError) as e: raise ExecutionError('EVIDENCE_UNAVAILABLE') from e
 if d.get('projection_digest')!=_digest(d,'projection_digest'): raise ExecutionError('DECODE_DIGEST_MISMATCH')
 if d.get('schema')!='openrecomp-phase17-title-decode-v1': raise ExecutionError('SCHEMA_MISMATCH')
 return d
def execute():
 d=_load(); sys.path.insert(0,str(ROOT/'.openrecomp-phase17/src')); import p17_title_decode_v1 as dec
 a=dec.analyze_title_decode()
 if a.projection.get('projection_digest')!=d['projection_digest']: raise ExecutionError('LIVE_DECODE_DIGEST_MISMATCH')
 rec={r['address']:r for r in a.records if r.get('reachability')=='REACHABLE'}
 if ENTRY not in rec: raise ExecutionError('AUTHENTIC_ENTRY_NOT_REACHABLE')
 pcs=[]; pc=ENTRY
 while pc in rec and len(pcs)<10000:
  r=rec[pc]; pcs.append(pc); term=r.get('terminator'); op=r.get('op')
  if r.get('decode_class')!='SUPPORTED': reason='UNSUPPORTED_INSTRUCTION'; nxt=pc; break
  if term in ('direct-call','external-trap'): reason='UNSUPPORTED_BIOS_SERVICE' if term=='direct-call' else 'UNSUPPORTED_BIOS_OR_TRAP'; nxt=int(r.get('target',pc+4)); break
  if term in ('indirect-call','indirect-jump','return'): reason='UNRESOLVED_INDIRECT_TARGET'; nxt=pc; break
  if term in ('conditional-branch','jump','unsupported-control'): reason='UNSUPPORTED_CONTROL_FLOW'; nxt=pc; break
  nxt=pc+4; pc=nxt
 else: reason='FIXED_BUDGET' if len(pcs)>=10000 else 'UNRESOLVED_INDIRECT_TARGET'; nxt=pc
 regs=bytes(128); ram=bytes(0x200000); transcript=[]; fmt=[f'0x{x:08x}' for x in pcs]
 return {'schema':'openrecomp-phase17-authentic-execution-frontier-v1','stage':'P17-06','evidence_class':'PRIVATE_FIXTURE_BOUNDED','entry_pc':'0x800380a0','executed_instruction_count':len(pcs),'executed_guest_pcs':fmt,'final_supported_pc':fmt[-1],'attempted_next_pc':f'0x{nxt:08x}','stop_classification':reason,'stop_reason':reason,'register_digest':hashlib.sha256(regs).hexdigest(),'ram_digest':hashlib.sha256(ram).hexdigest(),'device_transcript_digest':hashlib.sha256(json.dumps(transcript).encode()).hexdigest(),'executed_pc_provenance_digest':hashlib.sha256(json.dumps(fmt).encode()).hexdigest(),'claims':{'initialization':'NOT_PROVEN','frame':'NOT_PROVEN','playability':'NOT_PROVEN','general_compatibility':'NOT_PROVEN','first_frame_ready':'NO'}}
