#!/usr/bin/env python3
"""UCM v2 unified CLI facade. Structural validation, not Gemini runtime interception.
No Drive writes. No direct media generation. Never certifies user approval or KB semantic use.
"""
import argparse,json,hashlib,sys,subprocess,zipfile,difflib
from pathlib import Path
from ucm_core.contracts import validate_prompt,validate_record,validate_video_plan,validate_gate,validate_kb_receipt,slice_master,sha
from ucm_core.migrate import migrate_preview
from ucm_core.delivery import validate_rendered_response
from ucm_core.drive_bridge import inspect_snapshot,prepare_update,verify_readback
from ucm_core.knowledge import section_map,retrieve_section
from ucm_core.portable import verify,validate_kb,build_zip,check_zip,preflight
from ucm_core.knowledge_gate import import_kb,connect_kb,verify_private,index_private,read_for_decision,decision_gate

def load(path):return json.loads(Path(path).read_text(encoding='utf8'))
def gate_if_pro(document,args,result):
 """Couple the normal output/gate validator to verified private KB evidence.
 Nothing in a model-authored JSON alone can authenticate a real tool execution.
 """
 mode=document.get('mode') if isinstance(document,dict) else None
 if mode not in {'STANDARD','PRO'}:
  return {'status':'BLOCKED','errors':['EXPLICIT_STANDARD_OR_PRO_MODE_REQUIRED'],'baseline':result,'production_approved':False}
 if mode=='STANDARD':
  return result
 stage=(document.get('stage') or document.get('current_gate') or document.get('stage_id'))
 if stage is None:
  return {'status':'BLOCKED','errors':['PROFESSIONAL_STAGE_REQUIRED'],'baseline':result,'production_approved':False}
 if isinstance(stage,str) and (stage.startswith('P0') or stage=='P1.0'):
  return result
 if not (getattr(args,'workspace',None) and getattr(args,'kb_plan',None) and getattr(args,'draft',None) and getattr(args,'skill_root',None)):
  return {'status':'BLOCKED','errors':['PROFESSIONAL_REQUIRES_ACTUAL_KB_GATE'],'baseline':result,'production_approved':False}
 kb=decision_gate(args.skill_root,args.workspace,args.kb_plan,args.draft)
 if kb['status']!='STRUCTURAL_KB_GROUNDING_PASS':
  return {'status':'BLOCKED','errors':['KNOWLEDGE_GATE_BLOCKED']+kb['errors'],'baseline':result,'kb':kb,'production_approved':False}
 if result.get('errors'):
  return result
 result['kb_gate']='STRUCTURAL_KB_GROUNDING_PASS'
 result['kb_draft_sha256']=kb['draft_sha256']
 return result

def main():
 p=argparse.ArgumentParser(prog='ucm',description='UCM v2 Portable RC6 unified validator (two modes, adaptive integrity)')
 sub=p.add_subparsers(dest='cmd',required=True)
 s=sub.add_parser('verify-release');s.add_argument('--skill-root',required=True);s.add_argument('--trusted-pin-sha256',required=True)
 s=sub.add_parser('audit-adaptive');s.add_argument('--skill-root',required=True);s.add_argument('--trusted-pin-sha256',required=True);s.add_argument('--baseline-zip');s.add_argument('--report',required=True)
 s=sub.add_parser('slice-master');s.add_argument('--master',required=True);s.add_argument('--stage',required=True);s.add_argument('--expected-sha256',required=True)
 s=sub.add_parser('check-prompt');s.add_argument('--packet',required=True);s.add_argument('--skill-root');s.add_argument('--workspace');s.add_argument('--kb-plan');s.add_argument('--draft')
 s=sub.add_parser('check-rendered');s.add_argument('--packet',required=True);s.add_argument('--response',required=True);s.add_argument('--skill-root');s.add_argument('--workspace');s.add_argument('--kb-plan');s.add_argument('--draft')
 s=sub.add_parser('check-gate');s.add_argument('--state',required=True);s.add_argument('--skill-root');s.add_argument('--workspace');s.add_argument('--kb-plan');s.add_argument('--draft')
 s=sub.add_parser('check-video-plan');s.add_argument('--record',required=True);s.add_argument('--skill-root');s.add_argument('--workspace');s.add_argument('--kb-plan');s.add_argument('--draft')
 s=sub.add_parser('check-project');s.add_argument('--record',required=True);s.add_argument('--record-id');s.add_argument('--folder-id');s.add_argument('--duplicate-count',type=int)
 s=sub.add_parser('check-kb-receipt');s.add_argument('--receipt',required=True);s.add_argument('--mode',required=True)
 s=sub.add_parser('drive-inspect');s.add_argument('--snapshot',required=True);s.add_argument('--snapshot-root',required=True)
 s=sub.add_parser('drive-prepare-update');s.add_argument('--snapshot',required=True);s.add_argument('--snapshot-root',required=True);s.add_argument('--proposed',required=True)
 s=sub.add_parser('drive-verify-readback');s.add_argument('--plan',required=True);s.add_argument('--snapshot',required=True);s.add_argument('--snapshot-root',required=True)
 s=sub.add_parser('p6-advanced');s.add_argument('--screenplay',required=True);s.add_argument('--master',required=True);s.add_argument('--expected-master-sha256',required=True);s.add_argument('--expected-contract-sha256',required=True);s.add_argument('--approved-lock');s.add_argument('--receipt')
 s=sub.add_parser('migrate-preview');s.add_argument('--records',nargs='+',required=True);s.add_argument('--folder-id',required=True);s.add_argument('--record-id',required=True);s.add_argument('--out',required=True)
 s=sub.add_parser('index-private-kb');s.add_argument('--file',required=True);s.add_argument('--role',required=True);s.add_argument('--out',required=True)
 s=sub.add_parser('read-private-kb');s.add_argument('--file',required=True);s.add_argument('--role',required=True);s.add_argument('--full-sha256',required=True);s.add_argument('--start',type=int,required=True);s.add_argument('--end',type=int,required=True);s.add_argument('--stage',required=True);s.add_argument('--decision-id',required=True);s.add_argument('--receipt-out',required=True);s.add_argument('--section-map',required=True);s.add_argument('--mode',choices=['PRO'],required=True)
 s=sub.add_parser('import-kb');s.add_argument('--skill-root',required=True);uploads=s.add_mutually_exclusive_group(required=True);uploads.add_argument('--upload-dir');uploads.add_argument('--files',nargs=6);s.add_argument('--workspace',required=True)
 s=sub.add_parser('kb-connect');s.add_argument('--skill-root',required=True);s.add_argument('--method',choices=['local','drive','chat'],required=True);source=s.add_mutually_exclusive_group(required=True);source.add_argument('--source-dir');source.add_argument('--files',nargs=6);s.add_argument('--workspace',required=True)
 s=sub.add_parser('verify-workspace-kb');s.add_argument('--skill-root',required=True);s.add_argument('--workspace',required=True)
 s=sub.add_parser('kb-index');s.add_argument('--skill-root',required=True);s.add_argument('--workspace',required=True);s.add_argument('--role',required=True);s.add_argument('--out',required=True)
 s=sub.add_parser('kb-read');s.add_argument('--skill-root',required=True);s.add_argument('--workspace',required=True);s.add_argument('--role',required=True);s.add_argument('--stage',required=True);s.add_argument('--decision-id',required=True);s.add_argument('--need-id',required=True);s.add_argument('--section-map',required=True);s.add_argument('--start',type=int,required=True);s.add_argument('--end',type=int,required=True);s.add_argument('--receipt-out',required=True)
 s=sub.add_parser('kb-check-decision');s.add_argument('--skill-root',required=True);s.add_argument('--workspace',required=True);s.add_argument('--plan',required=True);s.add_argument('--draft',required=True)
 s=sub.add_parser('validate-kb');s.add_argument('--skill-root',required=True)
 s=sub.add_parser('check-package');s.add_argument('--zip',required=True)
 s=sub.add_parser('build-upload');s.add_argument('--skill-root',required=True);s.add_argument('--trusted-pin-sha256',required=True);s.add_argument('--profile',choices=['public','professional'],required=True);s.add_argument('--out',required=True)
 s=sub.add_parser('preflight');s.add_argument('--skill-root',required=True);s.add_argument('--trusted-pin-sha256',required=True);s.add_argument('--mode',choices=['STANDARD','PRO'],required=True);s.add_argument('--workspace')
 a=p.parse_args()
 try:
  if a.cmd=='verify-release':
   print(json.dumps(verify(a.skill_root,a.trusted_pin_sha256),indent=2));return 0
  if a.cmd=='audit-adaptive':
   state=verify(a.skill_root,a.trusted_pin_sha256)
   root=Path(a.skill_root).resolve();report=Path(a.report).resolve()
   if report.is_relative_to(root):raise ValueError('ADAPTIVE_REPORT_MUST_BE_OUTSIDE_SKILL_ROOT')
   if report.exists():raise ValueError('ADAPTIVE_REPORT_ALREADY_EXISTS')
   result={'status':'ADAPTIVE_AUDIT_REVIEW_RECOMMENDED' if state['adaptive']['changes'] else 'ADAPTIVE_AUDIT_BASELINE',
           'integrity':state['status'],'adaptive':state['adaptive'],
           'semantic_safety':'NOT_AUTOMATICALLY_PROVEN','automated_policy_review':'GUARD_HASH_ONLY'}
   if a.baseline_zip:
    with zipfile.ZipFile(a.baseline_zip) as z:
     if z.testzip() is not None:raise ValueError('BASELINE_ARCHIVE_CORRUPTED')
     pin_record=load(root/'release_pin.json')
     if sha(z.read('release_pin.json')) != a.trusted_pin_sha256:
      raise ValueError('UNTRUSTED_ADAPTIVE_BASELINE_RELEASE_PIN')
     baseline_skill=z.read('SKILL.md')
     if sha(baseline_skill) != pin_record['adaptive_baselines']['SKILL.md']:
      raise ValueError('UNTRUSTED_ADAPTIVE_BASELINE_SKILL')
     origin=baseline_skill.decode('utf-8').splitlines(keepends=True)
     current=(root/'SKILL.md').read_text(encoding='utf8').splitlines(keepends=True)
     diff=''.join(difflib.unified_diff(origin,current,fromfile='RELEASE/SKILL.md',tofile='INSTALLED/SKILL.md'))
     result['skill_diff']=diff[:300000]
     result['skill_diff_truncated']=len(diff)>300000
   report.parent.mkdir(parents=True,exist_ok=True)
   report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
   print(json.dumps({'status':result['status'],'report':str(report),'changes':len(state['adaptive']['changes']),'semantic_safety':'REVIEW_REQUIRED_IF_MODIFIED'},ensure_ascii=False,indent=2))
   return 0
  if a.cmd=='slice-master':
   raw=Path(a.master).read_bytes()
   if sha(raw)!=a.expected_sha256:raise ValueError('UNTRUSTED_MASTER_SHA256')
   print(slice_master(raw.decode('utf8'),a.stage));return 0
  if a.cmd=='validate-kb':r=validate_kb(a.skill_root)
  elif a.cmd=='check-package':r=check_zip(a.zip)
  elif a.cmd=='build-upload':r=build_zip(a.skill_root,a.out,a.trusted_pin_sha256,a.profile)
  elif a.cmd=='preflight':r=preflight(a.skill_root,a.trusted_pin_sha256,a.mode,a.workspace)
  elif a.cmd=='import-kb':r=import_kb(a.skill_root,a.upload_dir,a.workspace,a.files)
  elif a.cmd=='kb-connect':r=connect_kb(a.skill_root,a.method,a.workspace,a.source_dir,a.files)
  elif a.cmd=='verify-workspace-kb':r=verify_private(a.skill_root,a.workspace)
  elif a.cmd=='kb-index':r=index_private(a.skill_root,a.workspace,a.role,a.out)
  elif a.cmd=='kb-read':
   print(read_for_decision(a.skill_root,a.workspace,a.role,a.stage,a.decision_id,a.need_id,a.section_map,a.start,a.end,a.receipt_out));return 0
  elif a.cmd=='kb-check-decision':r=decision_gate(a.skill_root,a.workspace,a.plan,a.draft)
  elif a.cmd=='check-prompt':doc=load(a.packet);r=gate_if_pro(doc,a,validate_prompt(doc))
  elif a.cmd=='check-rendered':doc=load(a.packet);r=gate_if_pro(doc,a,validate_rendered_response(Path(a.response).read_text(encoding='utf8'),doc))
  elif a.cmd=='check-gate':doc=load(a.state);r=gate_if_pro(doc,a,validate_gate(doc))
  elif a.cmd=='drive-inspect':r=inspect_snapshot(load(a.snapshot),Path(a.snapshot_root))
  elif a.cmd=='drive-prepare-update':r=prepare_update(load(a.snapshot),Path(a.snapshot_root),load(a.proposed))
  elif a.cmd=='drive-verify-readback':r=verify_readback(load(a.plan),load(a.snapshot),Path(a.snapshot_root))
  elif a.cmd=='check-video-plan':doc=load(a.record);r=gate_if_pro(doc,a,validate_video_plan(doc))
  elif a.cmd=='check-project':r=validate_record(load(a.record),a.record_id,a.folder_id,a.duplicate_count)
  elif a.cmd=='check-kb-receipt':r=validate_kb_receipt(load(a.receipt),a.mode)
  elif a.cmd=='p6-advanced':
   root=Path(__file__).resolve().parent
   master=Path(a.master)
   if sha(master.read_bytes())!=a.expected_master_sha256:raise ValueError('UNTRUSTED_MASTER_SHA256')
   contract=root/'vendor_p6/contracts/P6_H01_H10_MASTER.json'
   if sha(contract.read_bytes())!=a.expected_contract_sha256:raise ValueError('UNTRUSTED_P6_CONTRACT_SHA256')
   if load(contract).get('origin_master_sha256')!=a.expected_master_sha256:raise ValueError('MASTER_CONTRACT_DRIFT')
   cmd=[sys.executable,str(root/'vendor_p6/run_validator.py'),'--screenplay',a.screenplay,'--master-source',str(master),'--trusted-contract-sha256',a.expected_contract_sha256]
   if a.approved_lock:cmd+=['--approved-lock',a.approved_lock]
   if a.receipt:cmd+=['--receipt',a.receipt]
   result=subprocess.run(cmd,capture_output=True,text=True,timeout=45)
   if result.returncode not in (0,1,2):raise ValueError('P6_PROCESS_ERROR:'+result.stderr[:150])
   print(result.stdout)
   return result.returncode
  elif a.cmd=='migrate-preview':
   rec=migrate_preview([load(x) for x in a.records],actual_folder_id=a.folder_id,record_file_id=a.record_id,source_raw_sha256=[sha(Path(x).read_bytes()) for x in a.records])
   Path(a.out).write_bytes(json.dumps(rec,ensure_ascii=False,indent=2,sort_keys=True).encode('utf8')+b'\n')
   r={'status':'MIGRATION_REVIEW_REQUIRED','output':a.out,'assets':len(rec['artifacts']),'warnings':rec['migration_warnings'],'production_approved':False}
  elif a.cmd=='index-private-kb':
   r=section_map(Path(a.file),a.role);Path(a.out).write_text(json.dumps(r,indent=2)+'\n');r={'status':'LOCAL_PRIVATE_KB_INDEXED','source_sha256':r['source_sha256'],'sections':len(r['section_ranges']),'production_approved':False}
  elif a.cmd=='read-private-kb':
   runtime_root=Path(__file__).resolve().parent.parent
   kb_state=validate_kb(runtime_root)
   if not kb_state['professional_available']:raise ValueError('ALL_SIX_VALIDATED_KB_REQUIRED')
   spec=load(runtime_root/'resources/PRIVATE_KB_SOURCE_PINS_ONLY.json')['private_kb_sources']
   if a.role not in spec or Path(a.file).resolve()!=(runtime_root/'knowledge_base'/spec[a.role]['filename']).resolve():raise ValueError('LEGACY_KB_READER_UNAVAILABLE_USE_KB_READ_WORKSPACE')
   from ucm_core.knowledge import verified_section_in_index
   verified_section_in_index(load(a.section_map),Path(a.file),a.role,a.start,a.end,a.full_sha256)
   excerpt,rec=retrieve_section(Path(a.file),a.full_sha256,a.start,a.end,source_id=a.role,stage=a.stage,decision_id=a.decision_id)
   Path(a.receipt_out).write_text(json.dumps(rec,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
   print(excerpt);return 0
  else:raise ValueError('UNKNOWN_COMMAND')
  print(json.dumps(r,ensure_ascii=False,sort_keys=True,indent=2));return 2 if r.get('status') in {'BLOCKED','KNOWLEDGE_GATE_BLOCKED'} else 0
 except (ValueError,KeyError,TypeError,OSError,json.JSONDecodeError,UnicodeError,AttributeError,OverflowError,subprocess.TimeoutExpired) as exc:
  print(json.dumps({'status':'BLOCKED','reason':str(exc),'production_approved':False},ensure_ascii=False));return 2
if __name__=='__main__':sys.exit(main())
