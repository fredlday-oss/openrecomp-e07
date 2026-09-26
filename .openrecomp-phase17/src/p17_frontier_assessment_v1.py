#!/usr/bin/env python3
from __future__ import annotations
import json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2];EXEC=ROOT/'.openrecomp-phase17/evidence/P17-06/authentic_execution.json'
class AssessmentError(ValueError):pass
def assess():
 try:d=json.loads(EXEC.read_text())
 except (OSError,json.JSONDecodeError) as e:raise AssessmentError('EXECUTION_EVIDENCE_UNAVAILABLE') from e
 if d.get('schema')!='openrecomp-phase17-authentic-execution-frontier-v1' or not d.get('executed_guest_pcs'):raise AssessmentError('EXECUTION_PREFIX_INVALID')
 keys=('gpu_writes','dma2','ordering_table_writes','ot_traversal','framebuffer_activity','initialization_predicates')
 return {'schema':'openrecomp-phase17-frontier-assessment-v1','stage':'P17-07','evidence_class':'PRIVATE_FIXTURE_BOUNDED','source':{'execution_prefix_digest':d['executed_pc_provenance_digest'],'device_transcript_digest':d['device_transcript_digest']},'frontier':{k:d[k] for k in ('entry_pc','final_supported_pc','attempted_next_pc','stop_reason','executed_instruction_count')},'observations':{k:{'encountered':False,'event_count':0,'basis':'P17-06 device transcript contains no event of this class'} for k in keys},'claims':{'initialization':'NOT_PROVEN','frame':'NOT_PROVEN','playability':'NOT_PROVEN','general_compatibility':'NOT_PROVEN','first_frame_ready':'NO'}}
