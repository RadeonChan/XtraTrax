"""Single-action preparation and transactional replacement of an existing soundtrack."""
from pathlib import Path
import json,tempfile,shutil
import patcher as p,lgu
import diagnostics
PLUGIN='SCRIPTS/NativeTrax.asi'

def paths(m):
 if m.get('version')==2:
  profile=lgu.PROFILES.get(m.get('target'));p.check(profile is not None,'Unknown backup profile.');lgu.validate_manifest(m,profile)
  return dict(m['installed_hashes']),{rel:(rel,h) for rel,h in profile['originals'].items()}
 p.check(m.get('version')==1 and m.get('exe_sha256')==p.EXE_SHA and m.get('original_sha256')==p.ORIGINAL_SHA,'Unsupported backup receipt.')
 return {'SDATA/sdat.viv':m['archive_sha256'],PLUGIN:m['plugin_sha256']},{'SDATA/sdat.viv':('sdat.viv',p.ORIGINAL_SHA)}

def backup_for(game):return Path(game)/'XtraTraxBackup'
def has_installation(game):return backup_for(game).exists()

def recover(game):
 """Resume rollback after an interrupted replacement; refuse unrelated changes."""
 game=Path(game);backup=backup_for(game);journal=backup/'replacement-recovery';marker=journal/'transaction.json'
 if not marker.exists():return
 tx=json.loads(marker.read_text(encoding='utf-8'));old=tx['previous'];new=tx['next'];old_files,_=paths(old);new_files,_=paths(new)
 p.check(set(old_files)==set(new_files) and old['exe_sha256']==new['exe_sha256']==p.sha(game/'SPEED2.EXE'),'Recovery target mismatch.')
 for rel,h in old_files.items():
  actual=p.sha(journal/rel)
  p.check(actual==h,f'Previous installation recovery copy failed verification: {rel}: expected {h}, got {actual}; size {(journal/rel).stat().st_size}; repeat {p.sha(journal/rel)}')
  p.check(not (game/rel).exists() or p.sha(game/rel) in [h,new_files[rel]],'Installed files changed outside XtraTrax; recovery stopped.')
 current=json.loads((backup/'receipt.json').read_text(encoding='utf-8'))
 p.check(current in [old,new],'Receipt changed outside XtraTrax; recovery stopped.')
 p.check(json.loads((journal/'previous-receipt.json').read_text(encoding='utf-8'))==old,'Previous receipt recovery copy failed verification; recovery stopped.')
 for rel,h in old_files.items():p.atomic_copy(journal/rel,game/rel);p.check(p.sha(game/rel)==h,'Recovery verification failed.')
 # Save original receipt bytes in the journal for exact restoration.
 p.atomic_copy(journal/'previous-receipt.json',backup/'receipt.json')
 # Explicit bounded path, validated before recursive removal.
 p.check(journal.resolve().parent==backup.resolve(),'Unexpected recovery directory.')
 shutil.rmtree(journal)

@diagnostics.operation("apply soundtrack")
def apply(game,tracks,wide_banners=False,progress=lambda s:None):
 game=Path(game).resolve();p.require_closed();recover(game);p.validate_game(game,False)
 backup=backup_for(game);previous=None
 if backup.exists():
  previous=json.loads((backup/'receipt.json').read_text(encoding='utf-8'));old_files,originals=paths(previous)
  p.check(p.sha(game/'SPEED2.EXE')==previous['exe_sha256'],'Installed executable changed.')
  for rel,h in old_files.items():p.check(p.sha(game/rel)==h,'Current soundtrack changed outside XtraTrax; replacement stopped.')
  for rel,(saved,h) in originals.items():p.check(p.sha(backup/saved)==h,'Original backup failed verification.')
 with tempfile.TemporaryDirectory(prefix='XtraTrax-prepare-') as tmp:
  temp=Path(tmp);source=game
  if previous:
   source=temp/'original-game';source.mkdir();shutil.copy2(game/'SPEED2.EXE',source/'SPEED2.EXE')
   for rel,(saved,h) in originals.items():
    dest=source/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(backup/saved,dest)
  package=temp/'prepared';m=p.build(source,tracks,package,progress,wide_banners=wide_banners)
  p.require_closed()
  if previous is None:
   progress('Backing up original music…');p.install(game,package);return m
  new_files,_=paths(m)
  p.check(set(new_files)==set(old_files) and m['exe_sha256']==previous['exe_sha256'],'Replacement profile mismatch.')
  for rel,h in old_files.items():p.check(p.sha(game/rel)==h,'Soundtrack changed during preparation; replacement stopped.')
  p.check(json.loads((backup/'receipt.json').read_text())==previous,'Receipt changed during preparation.')
  journal=backup/'replacement-recovery';p.check(not journal.exists(),'Existing recovery data needs inspection.')
  # Assemble recovery data off to the side. A copy failure leaves no active journal.
  with tempfile.TemporaryDirectory(prefix='replacement-pending-',dir=backup) as pending:
   staged=Path(pending)
   for rel,h in old_files.items():
    dest=staged/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(game/rel,dest)
    actual=p.sha(dest)
    p.check(actual==h,f'Recovery copy failed verification for {rel}; current installation unchanged. Expected {h}, got {actual}.')
   shutil.copy2(backup/'receipt.json',staged/'previous-receipt.json')
   p.check(p.sha(staged/'previous-receipt.json')==p.sha(backup/'receipt.json') and json.loads((staged/'previous-receipt.json').read_text(encoding='utf-8'))==previous,'Recovery receipt copy failed verification; current installation unchanged.')
   (staged/'transaction.json').write_text(json.dumps({'previous':previous,'next':m},indent=2),encoding='utf-8')
   staged.rename(journal)
  try:
   progress('Installing…');p.require_closed()
   for rel,h in new_files.items():p.atomic_copy(package/rel,game/rel);p.check(p.sha(game/rel)==h,'Installed verification failed.')
   p.atomic_copy(package/'native-trax.json',backup/'receipt.json')
  except Exception:
   recover(game);raise
  p.check(journal.resolve().parent==backup.resolve(),'Unexpected recovery directory.');shutil.rmtree(journal)
  return m

@diagnostics.operation("restore soundtrack")
def restore(game):
 p.require_closed();recover(Path(game).resolve());p.restore(game)
