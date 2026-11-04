"""Disposable S1-mini by Superwhisper worker using llama-cpp-python.

Heavy llama.cpp/model state lives only in this process. Metatron may terminate it
on idle or memory pressure. The worker keeps S1-mini's exact name and disables
thinking through the embedded Qwen3 chat template when supported.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

SYSTEM = (
    "You are a text normalizer for speech-to-text transcripts. The input begins "
    "with a control line specifying the styling, structure, and context settings; "
    "clean the transcript to match those settings and output only the cleaned text."
)


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--model',required=True); ap.add_argument('--n-ctx',type=int,default=2048); ap.add_argument('--n-gpu-layers',type=int,default=0)
    a=ap.parse_args()
    model=Path(a.model)
    if not model.is_file(): raise SystemExit(f'model not found: {model}')
    from llama_cpp import Llama
    llm=Llama(model_path=str(model),n_ctx=a.n_ctx,n_gpu_layers=a.n_gpu_layers,verbose=False)
    for line in sys.stdin:
        line=line.strip()
        if not line: continue
        rid=None
        try:
            req=json.loads(line); rid=req.get('id'); cmd=str(req.get('cmd') or ''); p=req.get('params') or {}
            if cmd=='shutdown':
                print(json.dumps({'id':rid,'ok':True,'result':True}),flush=True); return
            if cmd!='cleanup': raise ValueError(f'unknown command {cmd!r}')
            text=str(p.get('text') or '')
            styling=str(p.get('styling') or 'semi-formal'); structure=str(p.get('structure') or 'prose'); context=str(p.get('context') or 'general')
            control=f'[Styling: {styling}] [Structure: {structure}] [Context: {context}]'
            out=llm.create_chat_completion(
                messages=[{'role':'system','content':SYSTEM},{'role':'user','content':control+'\n'+text}],
                temperature=0.0,
                max_tokens=int(p.get('max_output_tokens') or 512),
                chat_template_kwargs={'enable_thinking':False},
            )
            content=str(out['choices'][0]['message']['content'] or '').strip()
            result={'text':content,'model':'S1-mini by Superwhisper','thinking':False}
            response={'id':rid,'ok':True,'result':result}
        except Exception as exc:
            response={'id':rid,'ok':False,'error':{'type':type(exc).__name__,'message':str(exc)}}
        print(json.dumps(response,separators=(',',':')),flush=True)
if __name__=='__main__': main()
