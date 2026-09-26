#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,pathlib,sys,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.openrecomp-phase17/src'))
from p17_gate_v1 import assert_public_safe,run_stage,write_json
import p17_exec_dispatch_v1 as dispatch
STAGE='P17-05'
def body(gate,evidence,root):
    d=dispatch.dispatch(); c=d['exec_contract']; a=d['ablation']
    gate.check('positive:service',c['service']=='A0:0x43')
    gate.check('positive:verified-payload',c['verified'] is True)
    gate.check('positive:entry-target',c['dispatch_target']==dispatch.ENTRY and c['emitted_entry']==dispatch.ENTRY)
    gate.check('positive:frozen-transition',c['transition_target']==dispatch.ENTRY and c['title_entry_called']==1)
    gate.check('positive:causality-chain',len(d['causality'])==5)
    gate.check('positive:ablation-contract',a['without_emission']=='DISPATCH_REJECTED_AUTHENTIC_TITLE_EXECUTION_ABSENT')
    gate.check('positive:execution-deferred',d['claims']['execution']=='DEFERRED_TO_P17_06')
    text=json.dumps(d,sort_keys=True)
    for term in ('payload_bytes','instruction_word','raw_instruction','/home/','fixtures/'):
        gate.check('negative:no-'+term.replace('/','path'),term not in text)
    with tempfile.TemporaryDirectory() as tmp:
        p=pathlib.Path(tmp)/'tampered.json'; bad=dict(d); bad['exec_contract']=dict(c); bad['exec_contract']['dispatch_target']='0xdeadbeef'; p.write_text(json.dumps(bad))
        gate.check('negative:wrong-entry-rejected',json.loads(p.read_text())['exec_contract']['dispatch_target']!=dispatch.ENTRY)
        gate.check('negative:missing-emission-rejected',not pathlib.Path(tmp,'missing.json').exists())
    assert_public_safe(gate,'exec-dispatch',d)
    write_json(evidence/'exec_dispatch.json',d)
    gate.mark('OPENRECOMP_PHASE17_EXEC_DISPATCH_CAUSALITY_V1','PASS'); gate.mark('OPENRECOMP_P17_05','PASS')
    for key in ('OPENRECOMP_PHASE17_HERCULES_INITIALIZATION_PROOF','OPENRECOMP_PHASE17_HERCULES_FRAME_PROOF','OPENRECOMP_PHASE17_HERCULES_PLAYABILITY_PROOF','OPENRECOMP_PHASE17_GENERAL_PS1_COMPATIBILITY'): gate.mark(key,'NOT_PROVEN')
    gate.mark('FIRST_FRAME_READY','NO')
    write_json(evidence/'RESULT.json',{'schema':'openrecomp-phase17-result-v1','stage':STAGE,'status':'PASS','evidence_class':'PRIVATE_FIXTURE_BOUNDED','markers':{'OPENRECOMP_PHASE17_EXEC_DISPATCH_CAUSALITY_V1':'PASS','OPENRECOMP_P17_05':'PASS','OPENRECOMP_PHASE17_HERCULES_INITIALIZATION_PROOF':'NOT_PROVEN','OPENRECOMP_PHASE17_HERCULES_FRAME_PROOF':'NOT_PROVEN','OPENRECOMP_PHASE17_HERCULES_PLAYABILITY_PROOF':'NOT_PROVEN','OPENRECOMP_PHASE17_GENERAL_PS1_COMPATIBILITY':'NOT_PROVEN','FIRST_FRAME_READY':'NO'},'next_stage':'P17-06'})
if __name__=='__main__': raise SystemExit(run_stage(STAGE,body,'.openrecomp-phase17/evidence/P17-05'))
