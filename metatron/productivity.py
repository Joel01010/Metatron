from __future__ import annotations
import time, uuid
from dataclasses import dataclass
from typing import Any
from .db import Database

_ALLOWED_STATUSES={"completed","failed","interrupted","injection_blocked"}
_ALLOWED_PRIVACY={"allow","no_context","pause"}
_ALLOWED_CONTEXT={"general","email","work","personal","code","terminal","notes"}
def _b(v:Any,n:int)->str:return str(v or "")[:max(0,int(n))]

@dataclass(slots=True)
class DictationHistory:
    db: Database; bus: Any|None=None
    def record(self,text:str,*,raw_text:str="",app_id:str="",app_name:str="",context_profile:str="general",language:str="en",model:str="",device_kind:str="",provider:str="",status:str="completed",duration_ms:float|None=None,error:str="",audio_path:str="",metadata:dict[str,Any]|None=None,pinned:bool=False)->dict[str,Any]:
        status=str(status).lower()
        if status not in _ALLOWED_STATUSES: raise ValueError(f"unsupported dictation status {status!r}")
        profile=str(context_profile or "general").lower(); profile=profile if profile in _ALLOWED_CONTEXT else "general"
        now=time.time(); item_id=uuid.uuid4().hex
        vals=(item_id,now,now,_b(raw_text,100000),_b(text,100000),_b(app_id,512),_b(app_name,512),profile,_b(language or 'en',32),_b(model,256),_b(device_kind,32).upper(),_b(provider,256),status,None if duration_ms is None else max(0,float(duration_ms)),_b(error,4000),1 if pinned else 0,_b(audio_path,2048),self.db.dumps(dict(metadata or {})))
        self.db.execute("""INSERT INTO dictation_history(id,created_at,updated_at,raw_text,text,app_id,app_name,context_profile,language,model,device_kind,provider,status,duration_ms,error,pinned,audio_path,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",vals)
        if self.bus:self.bus.emit("history.created","dictation",{"id":item_id,"status":status,"app_id":_b(app_id,512)})
        return self.get(item_id) or {}
    def _decode(self,row:dict[str,Any])->dict[str,Any]:
        out=dict(row); out['pinned']=bool(out.get('pinned')); out['metadata']=self.db.loads(out.pop('metadata_json','{}')); return out
    def get(self,item_id:str):
        rows=self.db.query("SELECT * FROM dictation_history WHERE id=?",(str(item_id),)); return self._decode(rows[0]) if rows else None
    def list(self,*,limit:int=100,offset:int=0,query:str="",status:str="",app_id:str="",pinned_only:bool=False):
        limit=min(max(1,int(limit)),500); offset=max(0,int(offset)); clauses=[]; params=[]
        if query:
            clauses.append("(text LIKE ? OR raw_text LIKE ? OR app_name LIKE ?)"); needle=f"%{str(query)[:500]}%"; params += [needle]*3
        if status: clauses.append("status=?"); params.append(str(status).lower())
        if app_id: clauses.append("app_id=?"); params.append(str(app_id))
        if pinned_only: clauses.append("pinned=1")
        where=" WHERE "+" AND ".join(clauses) if clauses else ""
        rows=self.db.query(f"SELECT * FROM dictation_history{where} ORDER BY pinned DESC,created_at DESC LIMIT ? OFFSET ?",(*params,limit,offset)); return [self._decode(r) for r in rows]
    def delete(self,item_id:str)->bool:
        cur=self.db.execute("DELETE FROM dictation_history WHERE id=?",(str(item_id),)); ok=bool(cur.rowcount and cur.rowcount>0)
        if ok and self.bus:self.bus.emit("history.deleted","user",{"id":str(item_id)})
        return ok
    def clear(self,*,keep_pinned:bool=True)->int:
        cur=self.db.execute("DELETE FROM dictation_history WHERE pinned=0" if keep_pinned else "DELETE FROM dictation_history"); count=int(cur.rowcount or 0)
        if self.bus:self.bus.emit("history.cleared","user",{"count":count,"keep_pinned":bool(keep_pinned)})
        return count
    def set_pinned(self,item_id:str,pinned:bool):
        self.db.execute("UPDATE dictation_history SET pinned=?,updated_at=? WHERE id=?",(1 if pinned else 0,time.time(),str(item_id))); return self.get(item_id)
    def stats(self)->dict[str,Any]:
        rows=self.db.query("""SELECT COUNT(*) total,SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) completed,SUM(CASE WHEN status!='completed' THEN 1 ELSE 0 END) issues,COALESCE(SUM(LENGTH(text)-LENGTH(REPLACE(text,' ',''))+CASE WHEN LENGTH(TRIM(text))>0 THEN 1 ELSE 0 END),0) words,COALESCE(SUM(duration_ms),0) duration_ms FROM dictation_history"""); r=rows[0] if rows else {}
        return {"total":int(r.get('total') or 0),"completed":int(r.get('completed') or 0),"issues":int(r.get('issues') or 0),"words":int(r.get('words') or 0),"duration_ms":float(r.get('duration_ms') or 0)}
    def prune(self,*,max_items:int=5000,older_than_days:int=30)->int:
        max_items=max(100,int(max_items)); cutoff=time.time()-max(1,int(older_than_days))*86400
        with self.db.transaction() as c:
            a=c.execute("DELETE FROM dictation_history WHERE pinned=0 AND created_at<?",(cutoff,)).rowcount or 0
            b=c.execute("DELETE FROM dictation_history WHERE pinned=0 AND id IN (SELECT id FROM dictation_history WHERE pinned=0 ORDER BY created_at DESC LIMIT -1 OFFSET ?)",(max_items,)).rowcount or 0
        return int(a+b)

@dataclass(slots=True)
class VocabularyStore:
    db:Database; bus:Any|None=None
    def list(self,*,query:str="",limit:int=500):
        limit=min(max(1,int(limit)),1000)
        if query:
            n=f"%{str(query)[:300]}%"; rows=self.db.query("SELECT * FROM vocabulary WHERE term LIKE ? OR replacement LIKE ? OR notes LIKE ? ORDER BY term LIMIT ?",(n,n,n,limit))
        else: rows=self.db.query("SELECT * FROM vocabulary ORDER BY term LIMIT ?",(limit,))
        return [self._decode(r) for r in rows]
    def upsert(self,term:str,*,replacement:str="",notes:str="",enabled:bool=True):
        term=_b(term.strip(),256)
        if not term: raise ValueError("vocabulary term cannot be empty")
        now=time.time(); ex=self.db.query("SELECT id,created_at,usage_count FROM vocabulary WHERE term=? COLLATE NOCASE",(term,)); item_id=str(ex[0]['id']) if ex else uuid.uuid4().hex; created=float(ex[0]['created_at']) if ex else now; usage=int(ex[0]['usage_count']) if ex else 0
        self.db.execute("""INSERT INTO vocabulary(id,term,replacement,notes,enabled,usage_count,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(term) DO UPDATE SET replacement=excluded.replacement,notes=excluded.notes,enabled=excluded.enabled,updated_at=excluded.updated_at""",(item_id,term,_b(replacement,512),_b(notes,2000),1 if enabled else 0,usage,created,now))
        if self.bus:self.bus.emit("vocabulary.changed","user",{"id":item_id,"term":term})
        return self.get(item_id) or {}
    def get(self,item_id):
        r=self.db.query("SELECT * FROM vocabulary WHERE id=?",(str(item_id),)); return self._decode(r[0]) if r else None
    def delete(self,item_id):
        cur=self.db.execute("DELETE FROM vocabulary WHERE id=?",(str(item_id),)); return bool(cur.rowcount and cur.rowcount>0)
    def enabled_terms(self,limit:int=1000): return [dict(r) for r in self.db.query("SELECT term,replacement FROM vocabulary WHERE enabled=1 ORDER BY usage_count DESC,term LIMIT ?",(min(max(1,int(limit)),5000),))]
    def observe_text(self,text:str)->int:
        h=str(text or '').casefold(); rows=self.db.query("SELECT id,term FROM vocabulary WHERE enabled=1") if h else []; matched=[str(r['id']) for r in rows if str(r['term']).casefold() in h]
        if matched:
            now=time.time(); self.db.executemany("UPDATE vocabulary SET usage_count=usage_count+1,updated_at=? WHERE id=?",((now,i) for i in matched))
        return len(matched)
    @staticmethod
    def _decode(r): out=dict(r); out['enabled']=bool(out.get('enabled')); return out

@dataclass(slots=True)
class AppRuleStore:
    db:Database; bus:Any|None=None
    def list(self): return [self._decode(r) for r in self.db.query("SELECT * FROM app_rules ORDER BY label,app_id")]
    def upsert(self,app_id:str,*,label:str="",privacy_action:str="allow",context_profile:str="general",enabled:bool=True,metadata:dict[str,Any]|None=None):
        app_id=_b(app_id.strip(),512).lower()
        if not app_id: raise ValueError('app_id cannot be empty')
        action=str(privacy_action).lower(); profile=str(context_profile).lower()
        if action not in _ALLOWED_PRIVACY: raise ValueError(f"privacy_action must be one of {sorted(_ALLOWED_PRIVACY)}")
        if profile not in _ALLOWED_CONTEXT: raise ValueError(f"context_profile must be one of {sorted(_ALLOWED_CONTEXT)}")
        now=time.time(); ex=self.db.query("SELECT created_at FROM app_rules WHERE app_id=? COLLATE NOCASE",(app_id,)); created=float(ex[0]['created_at']) if ex else now
        self.db.execute("""INSERT INTO app_rules(app_id,label,privacy_action,context_profile,enabled,metadata_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(app_id) DO UPDATE SET label=excluded.label,privacy_action=excluded.privacy_action,context_profile=excluded.context_profile,enabled=excluded.enabled,metadata_json=excluded.metadata_json,updated_at=excluded.updated_at""",(app_id,_b(label,512),action,profile,1 if enabled else 0,self.db.dumps(dict(metadata or {})),created,now))
        if self.bus:self.bus.emit("app_rule.changed","user",{"app_id":app_id,"privacy_action":action,"context_profile":profile})
        return self.evaluate(app_id)
    def delete(self,app_id):
        c=self.db.execute("DELETE FROM app_rules WHERE app_id=? COLLATE NOCASE",(str(app_id).lower(),)); return bool(c.rowcount and c.rowcount>0)
    def evaluate(self,app_id):
        key=str(app_id or '').strip().lower(); rows=self.db.query("SELECT * FROM app_rules WHERE app_id=? COLLATE NOCASE AND enabled=1",(key,)) if key else []
        if not rows:return {"app_id":key,"label":"","privacy_action":"allow","context_profile":"general","enabled":True,"metadata":{},"matched":False}
        out=self._decode(rows[0]); out['matched']=True; return out
    def _decode(self,row): out=dict(row); out['enabled']=bool(out.get('enabled')); out['metadata']=self.db.loads(out.pop('metadata_json','{}')); return out
