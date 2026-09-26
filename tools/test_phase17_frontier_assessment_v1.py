#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.openrecomp-phase17/src'))
from p17_gate_v1 import assert_public_safe,run_stage,write_json
import p17_frontier_assessment_v1 as a
STAGE='P17-07'
def body(g,e,r):
 try:x=a.assess();y=a.assess()
 except a.AssessmentError as err:g.fail('fail-closed',str(err));return
 g.check('deterministic',x==y);g.check('frontier',x['frontier']['stop_reason']=='UNSUPPORTED_CONTROL_FLOW')
 for k,v in x['observations'].items():g.check(k,v['encountered'] is False and v['event_count']==0)
 s=json.dumps(x,sort_keys=True)
 for t in ('/home/','payload_bytes','instruction_word','raw_instruction'):g.check('safe-'+t,t not in s)
 assert_public_safe(g,'assessment',x);write_json(e/'frontier_assessment.json',x);write_json(e/'determinism.json',{'equal':x==y,'sha256':hashlib.sha256(s.encode()).hexdigest()})
 marks={'OPENRECOMP_PHASE17_FRONTIER_ASSESSMENT_V1':'PASS','OPENRECOMP_P17_07':'PASS','OPENRECOMP_PHASE17_HERCULES_INITIALIZATION_PROOF':'NOT_PROVEN','OPENRECOMP_PHASE17_HERCULES_FRAME_PROOF':'NOT_PROVEN','OPENRECOMP_PHASE17_HERCULES_PLAYABILITY_PROOF':'NOT_PROVEN','OPENRECOMP_PHASE17_GENERAL_PS1_COMPATIBILITY':'NOT_PROVEN','FIRST_FRAME_READY':'NO'}
 for k,v in marks.items():g.mark(k,v)
 write_json(e/'RESULT.json',{'schema':'openrecomp-phase17-result-v1','stage':STAGE,'status':'PASS','evidence_class':'PRIVATE_FIXTURE_BOUNDED','markers':marks,'next_stage':'P17-90'})
if __name__=='__main__':raise SystemExit(run_stage(STAGE,body,'.openrecomp-phase17/evidence/P17-07'))
