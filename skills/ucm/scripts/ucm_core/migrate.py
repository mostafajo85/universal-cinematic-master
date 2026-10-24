"""Dry-run, loss-averse reconciliation. Never authenticates a model-authored approval."""
from __future__ import annotations
import json,re,uuid,hashlib
from pathlib import Path
from .contracts import canonical,validate_record
UUID=re.compile(r'^UCM-[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')

def migrate_preview(records:list[dict],*,actual_folder_id:str,record_file_id:str,source_raw_sha256:list[str]|None=None):
 if not records:raise ValueError('NO_SOURCE_RECORDS')
 folders={r.get('folder_id') or r.get('project_folder_id') for r in records}
 if folders!={actual_folder_id}:raise ValueError('CONFLICTING_FOLDER_IDS')
 names={r.get('name') for r in records}
 if len(names)!=1:raise ValueError('CONFLICTING_PROJECT_NAMES')
 old_ids=[r.get('project_id') for r in records]
 uuid_ids=[v for v in old_ids if isinstance(v,str) and UUID.fullmatch(v)]
 if len(set(uuid_ids))>1:raise ValueError('CONFLICTING_UUID_PROJECT_IDS')
 pid=uuid_ids[0] if uuid_ids else 'UCM-'+str(uuid.uuid5(uuid.NAMESPACE_URL,'ucm:folder:'+actual_folder_id))
 assets={};issues=[]; provenance=[]; by_storage={}
 checkpoints=[];checkpoints_keys=set()
 for ridx,r in enumerate(records):
  raw=canonical(r);ref={'source_project_id':r.get('project_id'),'normalized_json_sha256':hashlib.sha256(raw).hexdigest()}
  if source_raw_sha256 is not None:ref['source_record_sha256']=source_raw_sha256[ridx]
  provenance.append(ref)
  for cp in r.get('checkpoints',[]):
   k=hashlib.sha256(canonical(cp)).hexdigest()
   if k not in checkpoints_keys:checkpoints.append({'legacy_checkpoint':cp,'source_sha256':ref.get('source_record_sha256',ref['normalized_json_sha256']),'authenticity':'NOT_VERIFIED'});checkpoints_keys.add(k)
  for a in r.get('artifacts',[]):
   fid=a.get('stored_file_id'); digest=a.get('sha256');aid=a.get('artifact_id')
   if not fid or not digest or not aid:raise ValueError('INCOMPLETE_ARTIFACT_PROVENANCE')
   if fid in by_storage and by_storage[fid] != digest:raise ValueError('CONFLICTING_MEDIA_HASH:'+fid)
   by_storage[fid]=digest
   rec=assets.setdefault(fid,{'artifact_id':aid,'stored_file_id':fid,'stored_parent_id':a.get('stored_parent_id'),
    'sha256':digest,'filename':a.get('stored_filename') or a.get('original_filename'),
    'role':a.get('role') or a.get('category'),'revision':str(a.get('revision','UNKNOWN')),
    'media_state':'NOT_INSPECTED','approval_state':'PENDING_USER_APPROVAL','approval_claims':[],'legacy_source_records':[],
    'external_approval_evidence':None})
   if rec['artifact_id']!=aid or rec['stored_parent_id']!=a.get('stored_parent_id'):
    raise ValueError('CONFLICTING_MEDIA_IDENTITY:'+fid)
   if rec['filename']!=(a.get('stored_filename') or a.get('original_filename')):issues.append('ALIAS_FILENAME_MISMATCH:'+fid)
   claim={'legacy_record_sha256':ref.get('source_record_sha256',ref['normalized_json_sha256']),
     'qa_status':a.get('qa_status') or a.get('state'),
     'approval_status':a.get('user_approval_status'),
     'approval_receipt':a.get('user_approval_receipt'),
     'reported_inspection':a.get('inspection',{}),
     'user_approval_external_verified':False}
   if a.get('user_approval_status')=='NOT_APPROVED':rec['approval_state']='NOT_APPROVED'
   rec['approval_claims'].append(claim)
   rec['legacy_source_records'].append(ref.get('source_record_sha256',ref['normalized_json_sha256']))
   if (a.get('qa_status')=='QA_PASS' or a.get('inspection')): rec['media_state']='CLAIMED_INSPECTED_NOT_VERIFIED'
  if r.get('p6_approval_receipt'):issues.append('P6_CLAIM_REQUIRES_PROVENANCE_VERIFICATION')
 if len(records)>1:issues.append('DUPLICATE_SOURCE_RECORDS_REQUIRE_RECONCILIATION')
 for a in assets.values():
  statuses={str(x['approval_status'] or ('ACCEPTED' if x['reported_inspection'] and x['qa_status']=='ACCEPTED' else 'UNSPECIFIED')) for x in a['approval_claims']}
  if len(statuses)>1:issues.append('CONFLICTING_ASSET_APPROVAL_CLAIMS:'+a['stored_file_id'])
  if any(x['approval_status']=='USER_APPROVED' or x['approval_receipt'] for x in a['approval_claims']):
   a['approval_state']='CLAIMED_NOT_AUTHENTICATED'
 data={'schema':'ucm.project.record.v2','project_id':pid,'name':records[0]['name'],
  'folder_id':actual_folder_id,'record_file_id':record_file_id,
  'artifacts':list(assets.values()),'checkpoints':checkpoints,'gate_receipts':{},'events':[],
  'canonical_locks':{},'revision':1,'status':'MIGRATION_REVIEW_REQUIRED',
  'legacy_aliases':sorted(set(x for x in old_ids if x and x!=pid)),
  'legacy_sources':provenance,
  'migration_warnings':sorted(set(issues+['NO_HUMAN_APPROVAL_AUTOMATICALLY_MIGRATED','SCREENPLAY_TEXT_RETRIEVAL_UNVERIFIED']))}
 check=validate_record(data,actual_folder_id if False else record_file_id,actual_folder_id,duplicate_count=1)
 if check['errors']:raise ValueError('INTERNAL_MIGRATION_INVALID:'+repr(check['errors']))
 return data
