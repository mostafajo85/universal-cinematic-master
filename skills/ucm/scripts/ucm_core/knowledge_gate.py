"""Fail-closed Professional read/import and creative-decision evidence.
Structural evidence ≠ a proof of internal model cognition; output may be reviewed.
"""
from __future__ import annotations
import json,os,re,hashlib,tempfile,time
from pathlib import Path
from .portable import read_json, sha
from .knowledge import section_map,verified_section_in_index,retrieve_section
from .contracts import STAGES

ROLES={'CINE','PERF','REAL','TRANS','COMPAT','EXEC'}

def spec_for(root):
 return read_json(Path(root)/'resources/PRIVATE_KB_SOURCE_PINS_ONLY.json')['private_kb_sources']

def private_dir(workspace):return Path(workspace).resolve()/'knowledge_base'

def verify_private(root,workspace):
 spec=spec_for(root);folder=private_dir(workspace)
 errors=[];details={}
 if not folder.is_dir() or folder.is_symlink():return {'status':'BLOCKED','errors':['SIX_KB_WORKSPACE_MISSING'],'verified':False}
 if set(p.name for p in folder.iterdir())!={v['filename'] for v in spec.values()}:
  errors.append('KB_EXACT_SIX_REQUIRED')
 for role,v in spec.items():
  p=folder/v['filename']
  if not p.is_file() or p.is_symlink():errors.append('KB_NOT_FILE:'+role);continue
  b=p.read_bytes()
  try:
   decoded=b.decode('utf8')
   if not decoded.strip() or '\x00' in decoded:errors.append('INVALID_KB_TEXT:'+role)
  except UnicodeError:errors.append('NON_UTF8:'+role)
  if len(b)!=v['bytes'] or sha(b)!=v['source_sha256']:errors.append('KB_SOURCE_MISMATCH:'+role)
  details[role]={'bytes':len(b),'sha256':sha(b)}
 return {'status':'BLOCKED' if errors else 'VERIFIED_SIX_PRIVATE_SOURCES','errors':errors,'verified':not errors,'sources':details,'scope':'REAL_LOCAL_BYTES_ONLY'}

def import_kb(root,upload_dir,workspace,files=None):
 root=Path(root).resolve();w=Path(workspace).resolve()
 src=Path(upload_dir).resolve() if upload_dir else None
 if w==root or root in w.parents or w in root.parents:raise ValueError('WORKSPACE_MUST_BE_OUTSIDE_SKILL')
 if (src is None)==(files is None):raise ValueError('SELECT_EXACTLY_ONE_UPLOAD_SOURCE')
 if src is not None and (not src.is_dir() or src.is_symlink() or src==w):raise ValueError('UPLOAD_DIRECTORY_NOT_ACCESSIBLE')
 pin=spec_for(root);expect={v['filename'] for v in pin.values()}
 if files is not None:
  uploaded=[Path(x).resolve() for x in files]
  if len(uploaded)!=6 or {x.name for x in uploaded}!=expect:raise ValueError('UPLOAD_EXACT_SIX_FILES_REQUIRED')
  source_map={x.name:x for x in uploaded}
 else:
  if {q.name for q in src.iterdir()}!=expect:raise ValueError('UPLOAD_EXACT_SIX_FILES_REQUIRED')
  source_map={x.name:x for x in src.iterdir()}
 original={}
 for role,v in pin.items():
  f=source_map[v['filename']]
  if f.is_symlink() or not f.is_file():raise ValueError('UPLOAD_UNSAFE:'+role)
  b=f.read_bytes()
  if sha(b)!=v['source_sha256'] or len(b)!=v['bytes']:
   raise ValueError('UPLOAD_HASH_OR_SIZE_MISMATCH:'+role)
  try:
   if not b.decode('utf8').strip() or b'\x00' in b:raise ValueError('KB_EMPTY_OR_BINARY:'+role)
  except UnicodeError:raise ValueError('KB_NOT_UTF8:'+role)
  original[v['filename']]=b
 dest=w/'knowledge_base'
 if dest.exists():
  state=verify_private(root,w)
  if not state['verified']:raise ValueError('EXISTING_WORKSPACE_KB_CONFLICT')
  if any((dest/n).read_bytes()!=b for n,b in original.items()):raise ValueError('EXISTING_WORKSPACE_KB_DIFFERENT')
  return {'status':'ALREADY_IMPORTED_VERIFIED','workspace':str(w),'sources':state['sources'],'persistence':'CURRENT_WORKSPACE_ONLY'}
 w.mkdir(parents=True,exist_ok=True)
 tmp=Path(tempfile.mkdtemp(prefix='.ucm_kb_staging_',dir=w))
 try:
  for n,b in original.items():
   f=tmp/n
   with f.open('xb') as stream:
    stream.write(b);stream.flush();os.fsync(stream.fileno())
   if f.read_bytes()!=b:raise ValueError('KB_WRITE_READBACK_FAILED:'+n)
  # Atomic directory rename; dest was checked absent.
  if dest.exists():raise ValueError('CONCURRENT_KB_DESTINATION')
  tmp.rename(dest)
 except Exception:
  for f in tmp.glob('*'):f.unlink()
  if tmp.exists():tmp.rmdir()
  raise
 state=verify_private(root,w)
 if not state['verified']:raise ValueError('KB_IMPORTED_READBACK_FAILED')
 return {'status':'KB_IMPORTED_AND_VERIFIED','workspace':str(w),'sources':state['sources'],
         'persistence':'CURRENT_WORKSPACE_ONLY_REVERIFY_ON_RESUME', 'production_approved':False}

def index_private(root,workspace,role,out):
 state=verify_private(root,workspace)
 if not state['verified']:raise ValueError('KB_WORKSPACE_NOT_VERIFIED')
 spec=spec_for(root)
 if role not in spec:raise ValueError('UNKNOWN_KB_ROLE')
 kb=private_dir(workspace)/spec[role]['filename'];idx=section_map(kb,role)
 if not idx['section_ranges']:raise ValueError('NO_KB_SECTIONS_INDEXED:'+role)
 out=Path(out).resolve();w=Path(workspace).resolve()
 if not out.is_relative_to(w) or out.is_relative_to(private_dir(workspace)):
  raise ValueError('INDEX_MUST_REMAIN_IN_PRIVATE_WORKSPACE_OUTSIDE_KB_SOURCES')
 out.parent.mkdir(parents=True,exist_ok=True)
 out.write_text(json.dumps(idx,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
 return {'status':'KB_INDEXED','role':role,'sections':len(idx['section_ranges']),
         'source_sha256':idx['source_sha256'],'index':str(out),'boundary_status':idx['boundary_status']}

def read_for_decision(root,workspace,role,stage,decision_id,need_id,index,start,end,receipt_out):
 state=verify_private(root,workspace)
 if not state['verified']:raise ValueError('KB_WORKSPACE_NOT_VERIFIED')
 spec=spec_for(root)
 if role not in spec or stage not in STAGES or stage.startswith('P0_'):
  raise ValueError('INVALID_KB_DECISION_CONTEXT')
 if not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}',decision_id) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}',need_id):
  raise ValueError('INVALID_DECISION_OR_NEED_ID')
 source=private_dir(workspace)/spec[role]['filename'];idx=read_json(index)
 verified_section_in_index(idx,source,role,start,end,spec[role]['source_sha256'])
 excerpt,receipt=retrieve_section(source,spec[role]['source_sha256'],start,end,source_id=role,stage=stage,decision_id=decision_id)
 out=Path(receipt_out).resolve();w=Path(workspace).resolve()
 if not out.is_relative_to(w) or out.is_relative_to(private_dir(workspace)):
  raise ValueError('RECEIPT_MUST_REMAIN_IN_PRIVATE_WORKSPACE')
 if out.exists():raise ValueError('IMMUTABLE_RECEIPT_ALREADY_EXISTS')
 receipt.update(schema='ucm.kb.read.v4',need_id=need_id,source_relpath=spec[role]['filename'],
                start_line=start,end_line=end,read_at_ns=time.time_ns(),
                receipt_scope='RECONSTRUCTABLE_BYTE_READ_NOT_MODEL_THOUGHT_PROOF')
 out.parent.mkdir(parents=True,exist_ok=True)
 with out.open('x',encoding='utf8') as f:json.dump(receipt,f,indent=2,ensure_ascii=False)
 return excerpt

def decision_gate(root,workspace,plan,draft):
 state=verify_private(root,workspace)
 if not state['verified']:return {'status':'BLOCKED','errors':['SIX_KB_NOT_VERIFIED'], 'production_approved':False}
 plan=read_json(plan);draft_path=Path(draft).resolve();w=Path(workspace).resolve()
 if not draft_path.is_relative_to(w):raise ValueError('DRAFT_MUST_BE_IN_PRIVATE_WORKSPACE')
 output=draft_path.read_text('utf8');src_spec=spec_for(root)
 errors=[]
 if plan.get('expected_draft_sha256')!=sha(output.encode('utf8')):errors.append('DRAFT_REVISION_HASH_MISMATCH')
 if plan.get('mode')!='PRO':errors.append('PRO_MODE_REQUIRED')
 stage=plan.get('stage');decision=plan.get('decision_id')
 if stage not in STAGES or str(stage).startswith('P0_'):errors.append('INVALID_STAGE')
 if not isinstance(decision,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}',decision):errors.append('INVALID_DECISION_ID')
 needs=plan.get('needs')
 if not isinstance(needs,list) or not needs:errors.append('KNOWLEDGE_NEEDS_MISSING');needs=[]
 seen=set();reads=0
 for need in needs:
  if not isinstance(need,dict):errors.append('INVALID_NEED');continue
  nid=need.get('need_id')
  if not isinstance(nid,str) or not nid or nid in seen:errors.append('DUPLICATE_OR_MISSING_NEED');continue
  seen.add(nid);critical=need.get('critical')
  if critical not in (True,False):errors.append('NEED_CRITICALITY_MISSING:'+nid)
  if not critical and need.get('skip_reason') and not need.get('receipt_path'):continue
  role=need.get('role');rece=need.get('receipt_path')
  if not role in ROLES or not isinstance(rece,str) or not rece:errors.append('NEED_WITHOUT_SOURCE:'+nid);continue
  rp=Path(rece).resolve()
  if not rp.is_relative_to(w) or rp.is_relative_to(private_dir(workspace)) or not rp.is_file():
   errors.append('UNSAFE_OR_MISSING_RECEIPT:'+nid);continue
  receipt=read_json(rp)
  if any(receipt.get(a)!=b for a,b in {'schema':'ucm.kb.read.v4','role':role,'stage':stage,'decision_id':decision,'need_id':nid}.items()):
   errors.append('RECEIPT_CONTEXT_MISMATCH:'+nid);continue
  source=private_dir(workspace)/src_spec[role]['filename'];raw=source.read_bytes()
  if sha(raw)!=receipt.get('source_sha256'):errors.append('RECEIPT_SOURCE_MISMATCH:'+nid);continue
  lines=raw.decode('utf8').splitlines(keepends=True)
  start,end=receipt.get('start_line'),receipt.get('end_line')
  if not isinstance(start,int) or not isinstance(end,int) or not 1<=start<=end<=len(lines):
   errors.append('RECEIPT_INVALID_LINES:'+nid);continue
  excerpt=''.join(lines[start-1:end])
  if sha(excerpt.encode('utf8'))!=receipt.get('section_sha256'):
   errors.append('RECEIPT_SECTION_CONTENT_MISMATCH:'+nid);continue
  # Must link to actual index, not arbitrary snippet; re-derive source sections each gate.
  idx=section_map(source,role)
  if not any(x['start_line']==start and x['end_line']==end and x['section_sha256']==receipt['section_sha256'] for x in idx['section_ranges']):
   errors.append('RECEIPT_NOT_WHOLE_SECTION:'+nid);continue
  anchor=need.get('source_anchor');applied=need.get('applied_to');effect=need.get('effect')
  if not isinstance(anchor,str) or len(anchor.strip())<12 or anchor not in excerpt:
   errors.append('SOURCE_ANCHOR_NOT_READ:'+nid)
  if not isinstance(applied,str) or len(applied.strip())<12 or applied not in output:
   errors.append('NO_CONCRETE_OUTPUT_BINDING:'+nid)
  if not isinstance(effect,str) or len(effect.strip())<18:
   errors.append('NO_DECISION_EFFECT_EXPLANATION:'+nid)
  if receipt.get('read_at_ns',0)>draft_path.stat().st_mtime_ns:
   errors.append('DRAFT_PREDATES_SOURCE_READ:'+nid)
  reads+=1
 if reads==0:errors.append('NO_KB_READS')
 return {'status':'KNOWLEDGE_GATE_BLOCKED' if errors else 'STRUCTURAL_KB_GROUNDING_PASS',
         'errors':sorted(set(errors)),'roles_verified':sorted({n.get('role') for n in needs if isinstance(n,dict) and n.get('role') in ROLES}),
         'decision_id':decision,'stage':stage,'draft_sha256':sha(output.encode('utf8')),
         'reading_count':reads,'production_approved':False,
         'scope':'ACTUAL_READ_AND_OUTPUT_ANCHOR_CHECKED_NOT_PROOF_OF_MODEL_SEMANTIC_REASONING'}


def connect_kb(root, method, workspace, source_dir=None, files=None):
 """Host-neutral KB import; provider must first produce byte-readable local files.

 No network connection, Drive URL parsing, or attachment tool magic here.
 Evidence authenticates source bytes and private workspace roundtrip, not transport origin.
 """
 if method not in {'local','drive','chat'}:raise ValueError('UNKNOWN_KB_CONNECTION_METHOD')
 if (source_dir is None)==(files is None):raise ValueError('EXACTLY_ONE_SOURCE_DIR_OR_FILES_REQUIRED')
 if source_dir is not None:
  source_dir=str(source_dir)  # Accept pathlib.Path from local integration callers.
 if source_dir is not None and ('://' in source_dir or source_dir.startswith(('www.','gdrive:'))):
  raise ValueError('KB_REMOTE_URL_NOT_DOWNLOADED_HOST_MUST_STAGE_SIX_BYTES')
 if method=='drive' and source_dir is None:
  # Explicit staging for Drive connector downloads instead of fake remote file IDs.
  raise ValueError('DRIVE_METHOD_REQUIRES_HOST_DOWNLOADED_STAGING_DIRECTORY')
 if method=='drive' and files is not None:
  raise ValueError('DRIVE_METHOD_REQUIRES_HOST_DOWNLOADED_STAGING_DIRECTORY')
 r=import_kb(root, source_dir, workspace, files)
 # Deliberately never save links/tokens in the receipt; this method is user/host-supplied.
 r['method_selected']=method
 r['source_proof']='BYTE_IDENTITY_AND_LOCAL_PRIVATE_READBACK_ONLY'
 r['provider_origin_authenticated']=False
 r['no_context_injection']=True
 r['resume']='REVERIFY_WORKSPACE_ON_EVERY_NEW_SESSION'
 return r
