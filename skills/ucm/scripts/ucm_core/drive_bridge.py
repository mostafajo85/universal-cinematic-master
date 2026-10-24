"""Tool-agnostic, fail-closed Drive sync contract for an *isolated* host-side connector.
No credentials or network access; does not claim Drive roundtrip or user authorization.

Host must externally obtain a fresh folder listing and download the exact canonical
record bytes into an isolated snapshot, execute the proposed conditional write, then
supply fresh postwrite bytes/metadata for readback comparison. Google Drive is not a
transactional DB: conflicts detected here still require connector-side rechecking.
"""
from __future__ import annotations
import json,hashlib
from pathlib import Path
from .contracts import validate_record,report,sha,canonical

def _safe_rel(root:Path,name:str)->Path:
 p=Path(name)
 if p.is_absolute() or '..' in p.parts or not p.parts or '\\' in name:raise ValueError('UNSAFE_SNAPSHOT_PATH')
 target=(root/p).resolve()
 if not target.is_relative_to(root.resolve()):raise ValueError('SNAPSHOT_PATH_ESCAPE')
 return target

def _read(snapshot:dict,root:Path,entry:dict)->tuple[bytes,dict]:
 if entry.get('parent_id')!=snapshot.get('folder_id'):raise ValueError('SNAPSHOT_PARENT_MISMATCH')
 for field in ('id','name','blob','sha256'):
  if not entry.get(field):raise ValueError('SNAPSHOT_MISSING_'+field.upper())
 raw=_safe_rel(root,entry['blob']).read_bytes()
 if sha(raw)!=entry['sha256']:raise ValueError('SNAPSHOT_BLOB_HASH_MISMATCH')
 if 'version' in entry and (not isinstance(entry['version'],int) or entry['version']<1):raise ValueError('INVALID_REMOTE_VERSION')
 if entry.get('bytes') is not None and len(raw)!=entry['bytes']:raise ValueError('SNAPSHOT_SIZE_MISMATCH')
 return raw,entry

def inspect_snapshot(snapshot:dict, root:Path):
 """Explicitly rejects *both* zero and multiple records; never chooses newest."""
 errors=[]; folder=snapshot.get('folder_id');files=snapshot.get('files',[])
 if not folder:errors.append('SNAPSHOT_FOLDER_UNSPECIFIED')
 if not isinstance(files,list):return report(['FILES_NOT_LIST'],'OFFLINE_SNAPSHOT')
 ids=[f.get('id') for f in files if isinstance(f,dict)]
 if len(ids)!=len(set(ids)):errors.append('DUPLICATE_FILE_IDS')
 candidates=[f for f in files if isinstance(f,dict) and f.get('name')=='PROJECT_RECORD.json']
 if len(candidates)!=1:errors.append('CANONICAL_RECORD_COUNT_'+str(len(candidates)))
 entries={};record=None
 for f in files:
  if not isinstance(f,dict):errors.append('INVALID_FILE_ENTRY');continue
  try:
   b,meta=_read(snapshot,root,f);entries[f['id']]={'bytes':len(b),'sha256':sha(b),'version':f.get('version'),'name':f['name']}
   if f.get('name')=='PROJECT_RECORD.json' and len(candidates)==1:
    record=json.loads(b)
    errs=validate_record(record,record_id=f['id'],folder_id=folder,duplicate_count=len(candidates))['errors']
    errors+=['RECORD_'+x for x in errs]
  except (ValueError,TypeError,OSError,KeyError,json.JSONDecodeError) as ex:errors.append('FILE_INSPECTION_ERROR:'+str(ex))
 return report(errors,'OFFLINE_HOST_SUPPLIED_SNAPSHOT_NOT_LIVE_DRIVE',folder_id=folder,record_id=candidates[0].get('id') if len(candidates)==1 else None,entries=entries)

def prepare_update(snapshot:dict,root:Path,proposed:dict):
 checked=inspect_snapshot(snapshot,root)
 if checked['errors']:return report(checked['errors'],'UPDATE_PRECONDITION')
 entry=next(f for f in snapshot['files'] if f['name']=='PROJECT_RECORD.json')
 if not isinstance(entry.get('version'),int) or not snapshot.get('conditional_update_supported'):
  return report(['NO_ATOMIC_CAS_SUPPORTED_BY_DRIVE_HOST'],'UPDATE_PRECONDITION')
 raw=_read(snapshot,root,entry)[0]
 prior=json.loads(raw)
 errors=validate_record(proposed,record_id=entry['id'],folder_id=snapshot['folder_id'],duplicate_count=1)['errors']
 if proposed.get('project_id')!=prior.get('project_id'):errors.append('PROJECT_ID_CHANGED')
 if proposed.get('revision')!=prior.get('revision',-1)+1:errors.append('REVISION_NOT_INCREMENTED_BY_ONE')
 prior_map={a['stored_file_id']:a for a in prior['artifacts']}
 newer_map={a.get('stored_file_id'):a for a in proposed.get('artifacts',[])}
 for fid,a in prior_map.items():
  nxt=newer_map.get(fid)
  if not nxt:errors.append('OLD_ASSET_REMOVED:'+fid);continue
  if nxt.get('sha256')!=a.get('sha256'):errors.append('MEDIA_HASH_REPLACED:'+fid)
  if nxt.get('approval_state')=='EXTERNALLY_VERIFIED' and a.get('approval_state')!='EXTERNALLY_VERIFIED' and not nxt.get('external_approval_evidence'):
   errors.append('PROMOTED_APPROVAL_WITHOUT_EXTERNAL_EVIDENCE:'+fid)
 if errors:return report(errors,'UPDATE_PRECONDITION')
 proposal={'kind':'CONDITIONAL_DRIVE_UPDATE_PLAN_NOT_EXECUTED','record_id':entry['id'],'folder_id':snapshot['folder_id'],
  'expected_remote_version':entry['version'],'expected_old_sha256':entry['sha256'],
  'new_sha256':sha(canonical(proposed)),'new_revision':proposed['revision'],
  'required_host_actions':['fresh_list_folder_and_refuse_duplicate_name','fresh_read_id_and_compare_remote_version_and_sha256','connector_conditional_update_or_fail_closed','fresh_readback_and_validate'],
  'authorizes_write':False,'production_approved':False}
 return {'status':'PREPARED_NOT_EXECUTED','errors':[],'scope':'OFFLINE_WRITE_PLAN','plan':proposal,'production_approved':False}

def verify_readback(plan:dict,snapshot:dict,root:Path):
 """Can compare host-supplied postwrite bytes; not independent proof of host authenticity."""
 p=plan.get('plan',plan)
 check=inspect_snapshot(snapshot,root);e=list(check['errors'])
 if check.get('record_id')!=p.get('record_id'):e.append('POST_WRITE_RECORD_ID_MISMATCH')
 if check.get('folder_id')!=p.get('folder_id'):e.append('POST_WRITE_FOLDER_ID_MISMATCH')
 ent=check.get('entries',{}).get(p.get('record_id'),{})
 if ent.get('sha256')!=p.get('new_sha256'):e.append('POST_WRITE_HASH_MISMATCH')
 if not isinstance(ent.get('version'),int) or ent['version']<=p.get('expected_remote_version',1e30):e.append('POST_WRITE_VERSION_NOT_ADVANCED')
 return report(e,'HOST_SUPPLIED_READBACK_ONLY_NEEDS_INDEPENDENT_CONNECTOR_EVIDENCE')
