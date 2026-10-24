#!/usr/bin/env python3
import sys,argparse,json,hashlib
from pathlib import Path
from core.validator import audit,verdict,load,digest,CRITERIA
ROOT=Path(__file__).resolve().parent

def main():
 p=argparse.ArgumentParser();p.add_argument('--screenplay',required=True);p.add_argument('--approved-lock');p.add_argument('--master-source');p.add_argument('--trusted-contract-sha256');p.add_argument('--receipt');p.add_argument('--verify-receipt');a=p.parse_args()
 contract=load(ROOT/'contracts/P6_H01_H10_MASTER.json');candidate=load(a.screenplay);lock=load(a.approved_lock) if a.approved_lock else None
 records=audit(candidate,contract,lock)
 def rec(s,code,msg):records.append({'criterion':'TECH','status':s,'code':code,'message':msg,'evidence':[]})
 if not a.trusted_contract_sha256:rec('NOT_VERIFIED','UNPINNED_CONTRACT','Expected digest must be supplied from independently trusted anchor')
 elif hashlib.sha256((ROOT/'contracts/P6_H01_H10_MASTER.json').read_bytes()).hexdigest()!=a.trusted_contract_sha256:rec('FAIL','CONTRACT_CHANGED','Contract differs from independently trusted digest')
 if a.master_source:
  source=Path(a.master_source).read_bytes()
  if hashlib.sha256(source).hexdigest()!=contract['origin_master_sha256']:rec('FAIL','MASTER_SOURCE_CHANGED','Original master hash mismatch')
  else:
   import re
   text=source.decode()
   for c in contract['criteria']:
    m=re.search(r'^'+c['id']+r' ([^\n]+)',text,re.M)
    if not m or m.group(1)!=c['definition']:rec('FAIL','MASTER_CHECK_DRIFT',c['id'])
 code=hashlib.sha256(Path(__file__).read_bytes()+Path(ROOT/'core/validator.py').read_bytes()).hexdigest()
 receipt={'type':'RECOMPUTABLE_DIGEST_NOT_SIGNATURE','script_digest':digest(candidate),'contract_digest':digest(contract),'lock_digest':digest(lock) if lock else None,'code_digest':code,'records':records,'verdict':verdict(records)}
 receipt['self_digest']=digest(receipt)
 if a.verify_receipt:
  old=load(a.verify_receipt);orig=old.pop('self_digest',None)
  ok=orig==digest(old) and old=={k:v for k,v in receipt.items() if k!='self_digest'}
  print('RECOMPUTED_RECEIPT_MATCH' if ok else 'RECEIPT_INVALID_OR_STALE');return 0 if ok else 1
 if a.receipt:Path(a.receipt).write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 counts={v:sum(x['status']==v for x in records) for v in ('PASS','FAIL','NEEDS_REVIEW','NOT_VERIFIED')}
 print(json.dumps({'verdict':receipt['verdict'],'counts':counts,'screenplay_digest':receipt['script_digest'],'criteria_seen':sorted(set(x['criterion'] for x in records if x['criterion'] in CRITERIA))},ensure_ascii=False,indent=2))
 return 1 if receipt['verdict']=='NEEDS_FIX' else 2 if receipt['verdict']=='BLOCKED_PENDING_EVIDENCE' else 0
if __name__=='__main__':sys.exit(main())
