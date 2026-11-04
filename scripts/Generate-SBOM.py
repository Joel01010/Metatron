#!/usr/bin/env python3
"""Generate a dependency/model inventory without installing an SBOM framework.

This is intentionally deterministic JSON that can be archived beside a release.
It is not a replacement for a signed CycloneDX/SPDX release manifest; it gives
release automation one small dependency-light source of truth.
"""
from __future__ import annotations
import argparse, hashlib, importlib.metadata, json, os, platform, subprocess, sys, tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()

def git_value(*args: str) -> str | None:
    try:
        return subprocess.check_output(['git',*args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip() or None
    except Exception:
        return None

def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument('--out', default=str(ROOT/'dist'/'metatron-sbom.json')); ns=ap.parse_args()
    pyproject=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8'))
    cargo=tomllib.loads((ROOT/'src-tauri'/'Cargo.toml').read_text(encoding='utf-8'))
    installed=[]
    for d in sorted(importlib.metadata.distributions(), key=lambda d:(d.metadata.get('Name') or '').lower()):
        name=d.metadata.get('Name');
        if name: installed.append({'name':name,'version':d.version})
    models=[]
    manifest=ROOT/'models.lock.json'
    if manifest.exists():
        raw=json.loads(manifest.read_text(encoding='utf-8'))
        models=raw.get('models',[]) if isinstance(raw,dict) else []
    local_model_env={
        'METATRON_KOKORO_MODEL':'kokoro', 'METATRON_KOKORO_VOICES':'kokoro-voices',
        'METATRON_PIPER_MODEL':'piper',
    }
    local=[]
    for env,name in local_model_env.items():
        value=os.environ.get(env,''); p=Path(value) if value else None
        if p and p.is_file(): local.append({'name':name,'path':str(p),'sha256':sha256(p),'bytes':p.stat().st_size})
    obj={
      'schema':'ai.metatron.sbom.v1', 'application':{'name':pyproject['project']['name'],'version':pyproject['project']['version'],'license':pyproject['project'].get('license')},
      'git':{'commit':git_value('rev-parse','HEAD'),'dirty':bool(git_value('status','--porcelain'))},
      'python':{'version':platform.python_version(),'declared':pyproject['project'].get('dependencies',[]),'installed_environment':installed},
      'rust':{'package':cargo.get('package',{}),'dependencies':cargo.get('dependencies',{}),'windows_dependencies':cargo.get("target",{}).get("cfg(windows)",{}).get('dependencies',{})},
      'models':models,'local_model_files':local,
      'notes':['Model weights are not redistributed by default. Verify models.lock.json and docs/LICENSE_GATE.md before release.']
    }
    out=Path(ns.out); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(obj,indent=2,sort_keys=True)+"\n",encoding='utf-8'); print(out); return 0
if __name__=='__main__': raise SystemExit(main())
