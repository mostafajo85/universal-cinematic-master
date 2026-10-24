"""Private KB selective retrieval: full source is read locally, only selected source sections emitted.
No protected KB text belongs in public distributions, maps or project records.
"""
from __future__ import annotations
import hashlib,json,re
from pathlib import Path
from .contracts import sha

def section_map(file:Path, source_id:str):
 """Build nested-heading boundaries. Never use ordinary numbered list items as headings.

 A section spans to the next heading with level <= its own, preserving child text.
 Machine-detected boundaries require source review before claiming semantic completeness.
 """
 content=file.read_bytes();lines=content.decode('utf8').splitlines(keepends=True)
 heads=[]
 for i,line in enumerate(lines):
  s=line.rstrip('\r\n').strip()
  m=re.match(r'^(#{1,4})[ \t]+(\S.*)$',s)
  if m:
   heads.append((i+1,len(m.group(1)),m.group(2)))
  elif source_id in {'PERF','REAL'} and i>0 and i+1<len(lines):
   # Plain-text modules use a rule-delimited chapter format instead of Markdown.
   # Both the preceding AND following line must be separator rules so ordinary
   # uppercase prose/labels cannot become chapter boundaries.
   before=lines[i-1].strip(); after=lines[i+1].strip()
   if (len(s)>=6 and len(s)<=140 and s==s.upper() and
       re.fullmatch(r'[=\-]{12,}',before) and re.fullmatch(r'[=\-]{12,}',after) and
       not re.fullmatch(r'[=\-]+',s)):
    heads.append((i+1,1,s))
  # REAL principle IDs are standalone all-caps headings and often unruled.
  if source_id=='REAL' and re.fullmatch(r'RI-\d{2}(?:\.\d+)?[ \t]+[A-Z][A-Z0-9_ /\-]{4,}',s):
   if not any(h[0]==i+1 for h in heads):heads.append((i+1,2,s))
 ranges=[]
 for j,(start,level,title) in enumerate(heads):
  end=len(lines)
  for next_start,next_level,_ in heads[j+1:]:
   if next_level<=level:
    end=next_start-1
    break
  span=''.join(lines[start-1:end]).encode('utf8')
  number=re.match(r'^(\d{1,2}(?:\.\d{1,2})*(?:\.[A-Z])?|RI-\d+|AT-\d+)\b',title)
  section_id=(source_id+':'+number.group(1)) if number else (source_id+f':L{start}-L{end}')
  ranges.append({'section_id':section_id,'heading_level':level,'start_line':start,'end_line':end,'section_sha256':sha(span)})
 return {'source_id':source_id,'source_sha256':sha(content),'source_bytes':len(content),
  'index_version':'heading-hierarchy-v3','boundary_status':'MACHINE_DERIVED_REVIEW_REQUIRED',
  'section_ranges':ranges}

def retrieve_section(file:Path,observed_full_sha:str,start:int,end:int,*,source_id:str,stage:str,decision_id:str):
 b=file.read_bytes()
 if sha(b)!=observed_full_sha:raise ValueError('KB_SOURCE_SHA_MISMATCH')
 ls=b.decode('utf8').splitlines(keepends=True)
 if not isinstance(start,int) or not isinstance(end,int) or not (1<=start<=end<=len(ls)):
  raise ValueError('INVALID_SECTION_LINES')
 excerpt=''.join(ls[start-1:end])
 if len(excerpt.encode('utf8'))>30000:raise ValueError('SECTION_TOO_LARGE_REFINE_SELECTION')
 evidence={'role':source_id,'stage':stage,'decision_id':decision_id,'section_id':f'L{start}-L{end}',
  'source_sha256':sha(b),'section_sha256':sha(excerpt.encode('utf8')),'source_bytes':len(b),
  'actual_source_read':True,'before_draft':True,'applied_to':'PENDING_ACTUAL_DECISION','claim_only':False,
  'receipt_scope':'LOCAL_FILE_BYTES_SEEN_NOT_PROOF_OF_MODEL_USE'}
 return excerpt,evidence


def verified_section_in_index(index:dict,source:Path,role:str,start:int,end:int,expected_sha:str):
 """Prevent arbitrary cherry-picked KB lines posing as a complete section."""
 if index.get('index_version')!='heading-hierarchy-v3':raise ValueError('UNTRUSTED_KB_SECTION_INDEX_VERSION')
 if index.get('source_id')!=role or index.get('source_sha256')!=expected_sha:
  raise ValueError('KB_INDEX_SOURCE_MISMATCH')
 contents=source.read_bytes()
 if sha(contents)!=expected_sha:raise ValueError('KB_INDEX_STALE')
 lines=contents.decode('utf8').splitlines(keepends=True)
 actual=''.join(lines[start-1:end]).encode('utf8')
 if not any((x.get('start_line'),x.get('end_line'),x.get('section_sha256'))==(start,end,sha(actual)) for x in index.get('section_ranges',[])):
  raise ValueError('KB_SECTION_NOT_COMPLETE_INDEXED_SECTION')
 return True
