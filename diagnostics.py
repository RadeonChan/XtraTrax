"""Local failure evidence. Reports contain paths/metadata, never file contents."""
from pathlib import Path
from datetime import datetime,timezone
import os,json,tempfile,uuid,traceback,functools,hashlib
VERSION='0.3.11'

def file_state(path, *, digest=False):
 p=Path(path);result={'path':str(p)}
 try:
  s=p.stat();result.update(size=s.st_size,mtime_ns=s.st_mtime_ns)
  if digest and p.is_file():
   with p.open('rb') as f:result['sha256']=hashlib.file_digest(f,'sha256').hexdigest()
 except OSError as e:result['inspection_error']=str(e)
 return result

def save(error,operation,detail=None):
 """Diagnostics must never replace the primary exception or prevent rollback."""
 try:
  folder=Path(os.environ.get('LOCALAPPDATA',tempfile.gettempdir()))/'XtraTrax/Diagnostics';folder.mkdir(parents=True,exist_ok=True)
  report={'version':VERSION,'utc':datetime.now(timezone.utc).isoformat(),'operation':operation,'error_type':type(error).__name__,'error':str(error),'traceback':''.join(traceback.format_exception(error)),'details':detail or {},'earlier_report':getattr(error,'xtratrax_report',None)}
  path=folder/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex+'.json')
  with path.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
  error.xtratrax_report=str(path)
  error.add_note('XtraTrax diagnostic report: '+str(path))
  return path
 except Exception:
  return None

def describe(error):
 path=getattr(error,'xtratrax_report',None)
 return str(error)+(('\n\nDiagnostic report: '+path) if path else '')

def operation(name):
 def decorate(fn):
  @functools.wraps(fn)
  def wrapped(game,*args,**kwargs):
   try:return fn(game,*args,**kwargs)
   except Exception as e:
    detail={'game_folder':str(game),'files':[]}
    try:
     for rel in ['SPEED2.EXE','SDATA/sdat.viv','PFDATA/MusicSFx.mpf','PFDATA/MusicSFx.mus','SCRIPTS/NativeTrax.asi','XtraTraxBackup/receipt.json']:
      path=Path(game)/rel
      if path.exists():detail['files'].append(file_state(path,digest=True))
     receipt=Path(game)/'XtraTraxBackup/receipt.json'
     if receipt.exists() and receipt.stat().st_size<4*1024*1024:
      saved=json.loads(receipt.read_text(encoding='utf-8'))
      detail['receipt_hashes']={key:saved[key] for key in ['exe_sha256','original_sha256','archive_sha256','plugin_sha256','original_hashes','installed_hashes'] if key in saved}
    except Exception:pass
    save(e,name,detail);raise
  return wrapped
 return decorate
