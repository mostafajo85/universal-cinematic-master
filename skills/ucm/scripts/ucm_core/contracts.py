"""UCM v2.0 RC1 deterministic *structural* gates. Not a Gemini UI interceptor."""
from __future__ import annotations
import hashlib, json, math, re
from pathlib import Path

STAGES=['P0_LANGUAGE','P0_MODE','P0_PROJECT','P1.0','P1','P2','P3','P4','P5','P6','P7','P8.0','P8.1','P8.2','P8.3','P8.4','P8.5','P8.6','P9','P10','P11']
DEPENDENCIES={s:STAGES[:i] for i,s in enumerate(STAGES)}
BINS=(4,6,8,10)
HEX64=re.compile(r'^[a-f0-9]{64}$')
VALID_KB={'CINE','PERF','REAL','TRANS','COMPAT','EXEC'}
PROMPT_META=re.compile(r'\b(?:ATTACH_REQUIRED|CONTEXT_ONLY|REFERENCE_MANIFEST|REFERENCE_ATTACHMENT_MANIFEST|KB_USAGE|USER_INSTRUCTIONS|ATTACHMENT\s+(?:LIST|FILES)|USER_APPROVAL|STORED_FILE_ID|PROJECT_RECORD|RECEIPT_IDS)\b',re.I)
FENCE=re.compile(r'(?m)^\s*```')

def sha(b:bytes)->str: return hashlib.sha256(b).hexdigest()
def canonical(d)->bytes:return (json.dumps(d,sort_keys=True,ensure_ascii=False,indent=2)+'\n').encode('utf8')
def _val(d,k):return isinstance(d,dict) and d.get(k) not in (None,'')
def report(codes,scope,**extra):
 codes=sorted(set(codes))
 return {'status':'BLOCKED' if codes else 'STRUCTURAL_PASS_NOT_EXTERNAL_AUTHENTICATION', 'errors':codes,'scope':scope,'production_approved':False,**extra}

def validate_record(p, record_id=None,folder_id=None, duplicate_count=None):
 e=[]
 if not isinstance(p,dict):return report(['PROJECT_NOT_OBJECT'],'DECLARED_PROJECT_STATE_ONLY')
 for k in ['project_id','folder_id','record_file_id','name']:
  if not isinstance(p.get(k),str) or not p[k].strip():e.append('INVALID_'+k.upper())
 if p.get('schema')!='ucm.project.record.v2':e.append('SCHEMA_V2_REQUIRED')
 if not isinstance(p.get('revision'),int) or isinstance(p.get('revision'),bool) or p['revision']<1:e.append('INVALID_RECORD_REVISION')
 if p.get('status') not in {'MIGRATION_REVIEW_REQUIRED','PROJECT_CREATED','ACTIVE','BLOCKED','ARCHIVED'}:e.append('INVALID_PROJECT_STATUS')
 for k in ['project_id','folder_id','record_file_id','name','artifacts','checkpoints','gate_receipts','events','canonical_locks','revision']:
  if not _val(p,k):e.append('MISSING_'+k.upper())
 if record_id is not None and p.get('record_file_id')!=record_id:e.append('RECORD_ID_MISMATCH')
 if folder_id is not None and p.get('folder_id')!=folder_id:e.append('FOLDER_ID_MISMATCH')
 if duplicate_count is not None and duplicate_count!=1:e.append('DUPLICATE_CANONICAL_RECORDS')
 if isinstance(p.get('artifacts'),list):
  ids=[]; stored=[]
  for i,a in enumerate(p['artifacts']):
   if not isinstance(a,dict):
    e.append('ASSET_NOT_OBJECT');continue
   ids.append(a.get('artifact_id'));stored.append(a.get('stored_file_id'))
   for k in ['artifact_id','stored_file_id','stored_parent_id','sha256','role','revision','filename','media_state','approval_state']:
    if not _val(a,k):e.append(f'ASSET_{i}_MISSING_'+k.upper())
   if _val(a,'sha256') and not HEX64.fullmatch(str(a['sha256'])):
    if a['sha256']!='HASH_NOT_VERIFIED' or a.get('media_state')!='NOT_INSPECTED' or a.get('approval_state')!='PENDING_USER_APPROVAL':e.append('INVALID_ASSET_HASH')
   if a.get('media_state') not in {'NOT_INSPECTED','CLAIMED_INSPECTED_NOT_VERIFIED','ACTUAL_FILE_VERIFIED','INSPECTED'}:e.append('INVALID_ASSET_MEDIA_STATE')
   if a.get('approval_state') not in {'PENDING_USER_APPROVAL','CLAIMED_NOT_AUTHENTICATED','EXTERNALLY_VERIFIED','NOT_APPROVED','STALE'}:
    e.append('INVALID_ASSET_APPROVAL_STATE')
   if a.get('approval_state')=='EXTERNALLY_VERIFIED' and not a.get('external_approval_evidence'):
    e.append('MISSING_EXTERNAL_APPROVAL_EVIDENCE')
   if (a.get('media_state') in {'NOT_INSPECTED','MISSING'} and a.get('approval_state')=='EXTERNALLY_VERIFIED'):
    e.append('APPROVAL_WITHOUT_INSPECTION')
  if len(ids)!=len(set(ids)):e.append('DUPLICATE_ARTIFACT_IDS')
  if len(stored)!=len(set(stored)):e.append('DUPLICATE_STORED_MEDIA')
 else:e.append('ARTIFACTS_NOT_LIST')
 if not isinstance(p.get('checkpoints'),list):e.append('CHECKPOINTS_NOT_LIST')
 if not isinstance(p.get('events'),list):e.append('EVENTS_NOT_LIST')
 if not isinstance(p.get('gate_receipts'),dict):e.append('RECEIPTS_NOT_OBJECT')
 if not isinstance(p.get('canonical_locks'),dict):e.append('LOCKS_NOT_OBJECT')
 return report(e,'DECLARED_PROJECT_STATE_ONLY')

def validate_gate(data):
 e=[];cur=data.get('current_gate');asked=data.get('asked_gates',[]); completed=data.get('completed_gates',[])
 if cur not in STAGES:e.append('UNKNOWN_GATE')
 if not isinstance(asked,list):e.append('ASKED_GATES_NOT_ARRAY')
 elif len(asked)>1:e.append('MULTIPLE_QUESTIONS_IN_TURN')
 elif asked and asked[0]!=cur:e.append('WRONG_GATE_QUESTION')
 if not isinstance(completed,list):e.append('COMPLETED_GATES_NOT_ARRAY');completed=[]
 if cur in STAGES and any(k not in completed for k in DEPENDENCIES[cur]):e.append('UNAPPROVED_UPSTREAM_GATES')
 if data.get('mode') not in (None,'STANDARD','PRO'):e.append('UNSUPPORTED_MODE')
 if cur=='P0_PROJECT' and data.get('mode')=='PRO' and not data.get('kb_runtime_verified'):e.append('PRO_KB_NOT_VERIFIED')
 if data.get('advanced') and not (data.get('validator_receipt') and data.get('user_decision_event')):e.append('UNAUTHORIZED_STAGE_ADVANCE')
 return report(e,'DECLARED_GATE_STATE_ONLY')

def validate_prompt(packet):
 e=[]
 if not isinstance(packet,dict):return report(['PACKET_NOT_OBJECT'],'PROMPT_PACKAGE')
 p=packet.get('generation_prompt'); manifest=packet.get('reference_manifest')
 if not isinstance(p,str) or not p.strip():e.append('MISSING_GENERATION_PROMPT');p=''
 if FENCE.search(p):e.append('FENCE_INSIDE_PROMPT')
 if PROMPT_META.search(p):e.append('METADATA_LEAK_IN_PROMPT')
 if re.search(r'(?i)\b[A-Za-z0-9_.-]+\.(?:jpg|jpeg|png|webp|pdf)\b',p):e.append('ATTACHMENT_FILENAME_LEAK_IN_PROMPT')
 if '\x00' in p:e.append('CONTROL_CHAR_IN_PROMPT')
 if manifest is None or not isinstance(manifest,list):e.append('MISSING_SEPARATE_REFERENCE_MANIFEST');manifest=[]
 names=set()
 for x in manifest:
  if not isinstance(x,dict) or not _val(x,'filename') or x.get('binding') not in {'ATTACH_REQUIRED','CONTEXT_ONLY'}:e.append('INVALID_REFERENCE_ITEM');continue
  if x['filename'] in names:e.append('DUPLICATE_REFERENCE');
  names.add(x['filename'])
 if packet.get('kind')=='SCENE_BOARD':
  if packet.get('production_ready'):
   if not packet.get('timing_approval_event_verified'):e.append('P8_1_TIMING_NOT_APPROVED')
   if not packet.get('reference_capability_verified'):e.append('REFERENCE_CARRIER_UNVERIFIED')
  n=packet.get('panels')
  if not isinstance(n,int) or isinstance(n,bool) or not 1<=n<=6:e.append('INVALID_STORYBOARD_PANEL_COUNT')
 if packet.get('kind')=='VIDEO':
  if packet.get('audio_route')!='VIDEO_NATIVE_AUDIO_ONLY':e.append('EXTERNAL_AUDIO_FORBIDDEN')
  if packet.get('native_audio_plan') not in {'SPOKEN','NO_DIALOGUE'}:e.append('NATIVE_AUDIO_PLAN')
  if packet.get('native_audio_plan')=='SPOKEN' and not (_val(packet,'dialogue_text') and _val(packet,'speaker_id')):e.append('NATIVE_DIALOGUE_BINDING')
  if packet.get('generation_seconds') not in BINS:e.append('INVALID_GENERATION_DURATION')
  if packet.get('production_ready'):
   if not packet.get('platform_capability_verified'):e.append('PLATFORM_CAPABILITY_NOT_VERIFIED')
   if not packet.get('actual_approved_board_id'):e.append('MISSING_ACTUAL_ACCEPTED_BLOCK_BOARD')
   if not packet.get('actual_approval_proof_verified'):e.append('UNVERIFIED_USER_APPROVAL')
  if any(x in packet for x in ('audio_master_id','external_audio_master','tts')):e.append('EXTERNAL_AUDIO_FORBIDDEN')
 if 'generation_seconds' in packet and packet.get('generation_seconds') not in BINS:e.append('INVALID_GENERATION_DURATION')
 if 'editorial_seconds' in packet:
  t=packet['editorial_seconds']
  if not isinstance(t,(int,float)) or isinstance(t,bool) or not math.isfinite(t) or t<=0:e.append('INVALID_EDITORIAL_DURATION')
 if packet.get('claimed_status') in {'MEDIA_APPROVED','PRODUCTION_APPROVED','USER_APPROVED'} and not packet.get('actual_approval_proof_verified'):
  e.append('FALSE_APPROVAL_CLAIM')
 return report(e,'STRUCTURED_OUTPUT_ONLY_CANNOT_INTERCEPT_GEMINI_UI')

def validate_kb_receipt(r,mode):
 e=[]
 if mode=='STANDARD':return report(['STANDARD_MUST_NOT_READ_PRIVATE_KB'] if r else [],'KB_PROVENANCE')
 if mode!='PRO':e.append('INVALID_MODE')
 if not isinstance(r,dict):return report(['MISSING_KB_RECEIPT'],'KB_PROVENANCE')
 if r.get('role') not in VALID_KB:e.append('INVALID_KB_ROLE')
 if not all(_val(r,k) for k in ('stage','source_sha256','section_sha256','section_id','before_draft','applied_to')):e.append('MISSING_KB_FIELDS')
 if r.get('before_draft') is not True:e.append('POST_DRAFT_RETRIEVAL')
 if not r.get('actual_source_read'):e.append('NO_SOURCE_READ_EVIDENCE')
 if r.get('claim_only'):e.append('SELF_REPORTED_ONLY')
 if _val(r,'section_sha256') and not HEX64.fullmatch(str(r['section_sha256'])):e.append('INVALID_SECTION_SHA256')
 return report(e,'STRUCTURAL_KB_RECEIPT_NOT_PROOF_OF_SEMANTIC_APPLICATION')

STAGE_SECTION={
'P0_LANGUAGE':'SETUP_P0_P5','P0_MODE':'SETUP_P0_P5','P0_PROJECT':'SETUP_P0_P5',
'P0':'SETUP_P0_P5','P1.0':'SETUP_P0_P5','P1':'SETUP_P0_P5','P2':'SETUP_P0_P5','P3':'SETUP_P0_P5','P4':'SETUP_P0_P5','P5':'SETUP_P0_P5',
'P6':'P6_SCREENPLAY','P7':'P7_ASSETS','P8':'P8_STORYBOARD','P8.0':'P8_STORYBOARD','P8.1':'P8_STORYBOARD','P8.2':'P8_STORYBOARD','P8.3':'P8_STORYBOARD','P8.4':'P8_STORYBOARD','P8.5':'P8_STORYBOARD','P8.6':'P8_STORYBOARD',
'P9':'P9_VIDEO','P10':'P10_P11_QA_EDIT','P11':'P10_P11_QA_EDIT'}

def _section(raw,key):
 begin='<!-- UCM_STAGE:'+key+':START -->';end='<!-- UCM_STAGE:'+key+':END -->'
 if raw.count(begin)!=1 or raw.count(end)!=1:raise ValueError('INVALID_MASTER_SECTION:'+key)
 part=raw.split(begin,1)[1].split(end,1)[0].strip()
 if not part:raise ValueError('EMPTY_MASTER_SECTION:'+key)
 return part

def _source_range(body,span):
 marker='<!-- SOURCE_V1_LINES:'+span+' -->'
 if marker not in body:raise ValueError('MISSING_NORMATIVE_SOURCE_RANGE:'+span)
 after=body.split(marker,1)[1]
 return after.split('<!-- SOURCE_V1_LINES:',1)[0].strip()

def slice_master(raw:str,stage:str):
 if stage=='GLOBAL':
  intro=raw.split('<!-- UCM_STAGE:CRITICAL_RUNTIME_POLICY:START -->',1)[0].strip()
  return intro+'\n\n'+_section(raw,'CRITICAL_RUNTIME_POLICY')+'\n\n'+_section(raw,'GLOBAL')+'\n'
 if stage=='KB':
  return raw.split('<!-- UCM_STAGE:GLOBAL:START -->',1)[0]+ '\n' + _section(raw,'PRIVATE_KB_POLICY')+'\n'
 if stage not in STAGE_SECTION:raise ValueError('UNKNOWN_STAGE')
 if raw.count('<!-- UCM_STAGE:GLOBAL:START -->')!=1 or raw.count('<!-- UCM_STAGE:GLOBAL:END -->')!=1:raise ValueError('INVALID_MASTER_ROOT')
 prelude=raw.split('<!-- UCM_STAGE:CRITICAL_RUNTIME_POLICY:START -->',1)[0].strip()
 parts=[prelude]
 kind=STAGE_SECTION[stage]
 body=_section(raw,kind)
 if kind=='P8_STORYBOARD' and stage!='P8':
  shared=_source_range(body,'293-311')
  long=_source_range(body,'538-605')
  desired=[ln for ln in long.splitlines() if ln.startswith(stage+' ')]
  if not desired:raise ValueError('MISSING_P8_SUBSTAGE:'+stage)
  parts+=['## P8 common contract\n'+shared,'## '+stage+' exact contract\n'+'\n'.join(desired)]
  # Relevant reference/continuity contract, not the full large memory section.
  cont=_section(raw,'CONTINUITY')
  if stage in {'P8.2','P8.4','P8.5'}:
   parts.append('## P4.4 authority\n'+_source_range(cont,'613-649').split('P4.4 PER-PROMPT',1)[1].split('P4.5 CARRIER',1)[0])
 elif kind=='SETUP_P0_P5':
  # Global instructions + setup are compact enough and all required decisions stay within one phase pack.
  parts.append(body)
 elif kind=='P7_ASSETS':
  parts.append(body)
  parts.append(_section(raw,'CONTINUITY'))
 elif kind in {'P9_VIDEO','P10_P11_QA_EDIT'}:
  parts.append(body);parts.append(_section(raw,'CONTINUITY'))
 else:parts.append(body)
 return '\n\n'.join(parts)+'\n'

def validate_video_plan(p):
 """Unified v2 schema, P8->P9 structural checks. No separate legacy project contract."""
 e=list(validate_record(p).get('errors',[]))
 if p.get('continuous_audio') or p.get('external_audio_master') or p.get('audio_master_id'):e.append('EXTERNAL_AUDIO_FORBIDDEN')
 assets={a.get('artifact_id'):a for a in p.get('artifacts',[]) if isinstance(a,dict)}
 blocks=p.get('blocks',[]);frames=p.get('frame_ids',[])
 if not isinstance(blocks,list) or not isinstance(frames,list):return report(e+['INVALID_BLOCKS_OR_FRAMES'],'VIDEO_PLAN_DECLARED_DATA')
 mapped=[];seen=[]
 def num(v):return isinstance(v,(float,int)) and not isinstance(v,bool) and math.isfinite(v)
 for b in blocks:
  bid=b.get('block_id')
  if not bid or bid in seen:e.append('DUPLICATE_BLOCK_ID')
  seen.append(bid)
  gen=b.get('generation_seconds')
  if gen not in BINS:e.append('LEGAL_DURATION')
  part=b.get('frame_ids',[]);mapped+=part
  start,end=b.get('edit_start'),b.get('edit_end')
  if not (num(start) and num(end) and 0<=start<end and gen in BINS and end-start<=gen):e.append('EDIT_DURATION')
  refs=b.get('references',[])
  if not isinstance(refs,list):e.append('INVALID_REFS');refs=[]
  # 10 effective slots is a V1 assumption and NOT a verified Flow claim.
  cost=sum(3 if x.get('role')=='CHARACTER_PACKAGE' else 1 for x in refs if x.get('binding')=='ATTACH_REQUIRED')
  if cost>10:e.append('REFERENCE_BUDGET_PLANNING_ASSUMPTION')
  if b.get('audio_route') not in (None,'VIDEO_NATIVE_AUDIO_ONLY'):e.append('AUDIO_ROUTE')
  if b.get('final_packet_ready'):
   if not b.get('platform_capability_verified'):e.append('PLATFORM_UNVERIFIED')
   if not all(b.get(k) for k in ('p6_approval_event_verified','timing_approval_event_verified','block_plan_approval_event_verified')):e.append('UPSTREAM_APPROVAL')
   for key,role in [('scene_board_ids','SCENE_STORYBOARD'),('block_board_ids','BLOCK_STORYBOARD')]:
    ids=b.get(key,[])
    if not ids:e.append('MISSING_'+key.upper())
    covered=[]
    for aid in ids:
     a=assets.get(aid,{})
     if a.get('role')!=role or a.get('approval_state')!='EXTERNALLY_VERIFIED' or a.get('media_state')!='INSPECTED':e.append('BOARD_NOT_ACCEPTED')
     covered+=a.get('frame_ids',[])
    if not all(f in covered for f in part):e.append('BOARD_FRAME_MAPPING')
   for ref in refs:
    if ref.get('binding')!='ATTACH_REQUIRED':continue
    a=assets.get(ref.get('artifact_id'),{})
    if not a or a.get('approval_state')!='EXTERNALLY_VERIFIED' or a.get('revision')!=ref.get('revision') or a.get('filename')!=ref.get('filename'):
     e.append('REFERENCE_STALE_OR_MISSING')
   for aid,rev in b.get('dependency_revisions',{}).items():
    if assets.get(aid,{}).get('revision')!=rev:e.append('STALE_DEPENDENCY')
   if b.get('previous_final_frame_required'):
    a=assets.get(b.get('previous_final_frame_id'),{})
    if a.get('role')!='LAST_ACCEPTED_FRAME_EVIDENCE' or a.get('approval_state')!='EXTERNALLY_VERIFIED':e.append('MISSING_PREVIOUS_FRAME')
   if b.get('audio_route')!='VIDEO_NATIVE_AUDIO_ONLY' or b.get('native_audio_plan') not in {'SPOKEN','NO_DIALOGUE'}:e.append('NATIVE_AUDIO_PLAN')
   if b.get('native_audio_plan')=='SPOKEN' and not (b.get('exact_dialogue_text') and b.get('speaker_ids')):e.append('NATIVE_DIALOGUE_BINDING')
 if mapped!=frames or len(frames)!=len(set(frames)):e.append('FRAME_COVERAGE_ORDER')
 return report(e,'STRUCTURED_PLAN_ONLY_NOT_AUTHENTICATED_MEDIA')
