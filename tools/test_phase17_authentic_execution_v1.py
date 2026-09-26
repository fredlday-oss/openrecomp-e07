#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.openrecomp-phase17/src'))
from p17_gate_v1 import assert_public_safe,run_stage,write_json
import p17_authentic_execute_v1 as ex
STAGE='P17-06'
def body(gate,evidence,root):
 try: one=ex.execute(); two=ex.execute()
 except ex.ExecutionError as err: gate.fail('fail-closed',str(err)); return
 gate.check('entry',one['entry_pc']=='0x800380a0');gate.check('prefix',one['executed_instruction_count']>0);gate.check('frontier',one['stop_reason'] in {'UNSUPPORTED_CONTROL_FLOW','UNRESOLVED_INDIRECT_TARGET','UNSUPPORTED_BIOS_SERVICE','UNSUPPORTED_BIOS_OR_TRAP','UNSUPPORTED_INSTRUCTION','FIXED_BUDGET'});gate.check('deterministic',one==two)
 assert_public_safe(gate,'exec',one);write_json(evidence/'authentic_execution.json',one);write_json(evidence/'determinism.json',{'equal':one==two,'sha256':hashlib.sha256(json.dumps(one,sort_keys=True).encode()).hexdigest()})
 marks={'OPENRECOMP_PHASE17_AUTHENTIC_EXECUTION_FRONTIER_V1':'PASS','OPENRECOMP_P17_06':'PASS','OPENRECOMP_PHASE17_HERCULES_INITIALIZATION_PROOF':'NOT_PROVEN','OPENRECOMP_PHASE17_HERCULES_FRAME_PROOF':'NOT_PROVEN','OPENRECOMP_PHASE17_HERCULES_PLAYABILITY_PROOF':'NOT_PROVEN','OPENRECOMP_PHASE17_GENERAL_PS1_COMPATIBILITY':'NOT_PROVEN','FIRST_FRAME_READY':'NO'}
 for k,v in marks.items():gate.mark(k,v)
 write_json(evidence/'RESULT.json',{'schema':'openrecomp-phase17-result-v1','stage':STAGE,'status':'PASS','evidence_class':'PRIVATE_FIXTURE_BOUNDED','markers':marks,'frontier':{k:one[k] for k in ('final_supported_pc','attempted_next_pc','stop_reason','executed_instruction_count')},'next_stage':'P17-07'})
if __name__=='__main__':raise SystemExit(run_stage(STAGE,body,'.openrecomp-phase17/evidence/P17-06'))
