"""Check the *actual rendered user-visible text*, not merely a structured draft.
Cannot intercept Gemini: caller must actually run this before emitting output.
"""
from __future__ import annotations
import re
from .contracts import report,validate_prompt
FENCES=re.compile(r'(?ms)^```(?:text|english|en)?\s*\n(.*?)\n```\s*$',re.MULTILINE)
ANY_FENCE=re.compile(r'(?m)^```')

def validate_rendered_response(response:str,packet:dict):
 e=list(validate_prompt(packet)['errors'])
 if not isinstance(response,str):return report(e+['RENDERED_RESPONSE_NOT_TEXT'],'DISPLAYED_GENERATION_OUTPUT')
 spans=list(FENCES.finditer(response))
 if len(spans)!=1 or len(list(ANY_FENCE.finditer(response)))!=2:e.append('PROMPT_CODE_BLOCK_COUNT_OR_LANGUAGE')
 else:
  payload=spans[0].group(1)
  if payload!=packet.get('generation_prompt',''):
   e.append('RENDERED_CODE_BLOCK_NOT_EQUAL_TO_VALIDATED_PROMPT')
  before=response[:spans[0].start()]
  after=response[spans[0].end():]
  for ref in packet.get('reference_manifest',[]):
   if not isinstance(ref,dict):continue
   filename=ref.get('filename','')
   binding=ref.get('binding','')
   if filename and filename not in before:e.append('MISSING_EXTERNAL_REFERENCE_MANIFEST:'+filename)
   if filename and filename in after:e.append('REFERENCE_AFTER_CODE_BLOCK:'+filename)
   if binding and binding not in before:e.append('MISSING_REFERENCE_BINDING_OUTSIDE_CODE:'+filename)
  if not packet.get('generation_prompt'):e.append('EMPTY_CODE_PAYLOAD')
 return report(e,'RENDERED_TEXT_STRUCTURAL_ONLY_NOT_GEMINI_UI_INTERCEPT')
