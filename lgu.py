"""Verified loose-audio compatibility profiles. Shared encoding and map construction live in patcher."""
from pathlib import Path
import json,shutil,tempfile
EXE_SHA='82881d607ea8d90a2898ba9a6ed06da1ff6b56243f2e9146df30226fff69574b'
ORIGINALS={'PFDATA/MusicSFx.mpf':'4fe320440a0af5d8bcb7c31032607914aef9579b5c742d6caad9b4d6a046b772','PFDATA/MusicSFx.mus':'d48ac9a353f7340f1156aa64a0f9c69b7b68c3cb66ea15e624cb93ccf241a4f9'}
PLUGIN='SCRIPTS/NativeTrax.asi'

PROFILES={
 'lgu-loose':dict(target='lgu-loose',name='LGU',exe_sha256=EXE_SHA,originals=ORIGINALS,assets='lgu'),
 'magipack-loose':dict(target='magipack-loose',name='MagiPack',exe_sha256='f9dd86c054878ce6276beb07c1fd61874f7a1e4bf1f241b084c65b73e24168a7',originals={
  'PFDATA/MusicSFx.mpf':'c7b11862d9fb0811b1fdb2502e634801be9a544c70979c6abb915d18af658546',
  'PFDATA/MusicSFx.mus':'fe7bfa1a752f0444fb4d91473afe201d24718797bbfb60980dcb980a9b8520a0'},assets='us-loose')}

def is_loose(game):
 return any((game/rel).exists() for rel in ORIGINALS) or (game/'XtraTraxBackup/PFDATA').is_dir()

def profile_for(game):
 import patcher as p
 actual=p.sha(game/'SPEED2.EXE')
 for profile in PROFILES.values():
  if profile['exe_sha256']==actual:return profile
 raise ValueError('Unrecognized executable for loose music layout.')

def validate_original(game):
 import patcher as p
 profile=profile_for(game)
 p.check(not (game/'SDATA/sdat.viv').exists(),'Both active archive and loose music files are present. This mixed layout is not validated.')
 for rel,h in profile['originals'].items():p.check(p.sha(game/rel)==h,profile['name']+' requires its verified original loose music files. Restore the existing installation first.')

def build(game,tracks,output,progress,*,wide_banners=False):
 import patcher as p
 profile=profile_for(game)
 output=Path(output).resolve()
 p.check(1<=len(tracks)<=p.MAX_ADDED,'Add between 1 and 100 tracks (28–127 total).')
 p.check(not output.exists(),'Choose a new, empty output folder name.')
 p.check(not output.is_relative_to(game),'Build outside the game folder.')
 for t in tracks:
  p.inspect_audio(t['path'])
  for k in ['title','artist','album']:p.text_bytes(t[k])
 output.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='native-trax-lgu-',dir=output.parent) as tmp:
  temp=Path(tmp);records=[]
  minimum_size=(game/'PFDATA/MusicSFx.mus').stat().st_size
  for i,t in enumerate(tracks):
   progress(f'Encoding {i+1}/{len(tracks)}: {t["title"]}');records.append(p.encode(t,temp/f'{i}.asf',progress=p.track_progress(progress)))
   minimum_size+=(temp/f'{i}.asf').stat().st_size;p.check_soundtrack_size(minimum_size)
  p.check(len({r['key'] for r in records})==len(records),'Duplicate audio in the queue. Keep one copy so preferences remain unambiguous.')
  source=game/'PFDATA/MusicSFx.mus'
  # LGU offsets are not physically ordered. Duplicate final original sample beside
  # additions so the native adjacent-offset buffer estimate stays bounded.
  mus=p.expand_music((game/'PFDATA/MusicSFx.mpf').read_bytes(),source,0,source.stat().st_size,records,temp,relocate_last=True)
  p.check_soundtrack_size(mus.stat().st_size)
  stage=temp/'result';(stage/'PFDATA').mkdir(parents=True);(stage/'SCRIPTS').mkdir()
  for n in ['MusicSFx.mpf','MusicSFx.mus']:shutil.move(str(temp/n),str(stage/'PFDATA'/n))
  progress('Verifying loose audio and preparing its plugin…')
  hashes={rel:p.sha(stage/rel) for rel in profile['originals']}
  (stage/PLUGIN).write_bytes(p.make_plugin(records,hashes['PFDATA/MusicSFx.mus'],wide_banners,map_hash=hashes['PFDATA/MusicSFx.mpf'],template_profile=profile['assets']))
  hashes[PLUGIN]=p.sha(stage/PLUGIN)
  for r in records:r.pop('stream')
  m=dict(version=2,target=profile['target'],exe_sha256=profile['exe_sha256'],original_hashes=profile['originals'],installed_hashes=hashes,wide_banners=wide_banners,records=records)
  (stage/'native-trax.json').write_text(json.dumps(m,indent=2),encoding='utf-8');shutil.move(str(stage),str(output))
 return m

def validate_manifest(m,profile):
 import patcher as p
 p.check(m.get('version')==2 and m.get('target')==profile['target'] and m.get('exe_sha256')==profile['exe_sha256'] and m.get('original_hashes')==profile['originals'],'Package does not match this executable and loose-audio profile.')
 p.check(set(m.get('installed_hashes',{}))==set(profile['originals'])|{PLUGIN},'Unexpected loose-audio package contents.')

def install(game,package):
 import patcher as p
 profile=profile_for(game)
 package=Path(package);m=json.loads((package/'native-trax.json').read_text(encoding='utf-8'));validate_manifest(m,profile)
 for rel,h in m['installed_hashes'].items():p.check(p.sha(package/rel)==h,'Package failed integrity check.')
 p.check((game/'dinput8.dll').is_file(),'An existing dinput8 ASI loader is required.')
 p.check(not (game/PLUGIN).exists() and not (game/'SCRIPTS/Trax28.asi').exists(),'An existing soundtrack plugin is present. Restore/remove it first.')
 p.prepare_backup(game,{rel:(rel,h) for rel,h in profile['originals'].items()},m)
 try:
  for rel,h in m['installed_hashes'].items():
   p.atomic_copy(package/rel,game/rel);actual=p.sha(game/rel)
   p.check(actual==h,f'Installed verification failed for {rel}: expected {h}, got {actual}, repeated {p.sha(game/rel)}, package {p.sha(package/rel)}.')
 except Exception:
  restore(game);raise

def restore(game):
 import patcher as p
 profile=profile_for(game)
 backup=game/'XtraTraxBackup';m=json.loads((backup/'receipt.json').read_text(encoding='utf-8'));validate_manifest(m,profile)
 for rel,h in profile['originals'].items():
  p.check(p.sha(backup/rel)==h,'Backup failed verification.')
  p.check(not (game/rel).exists() or p.sha(game/rel) in [h,m['installed_hashes'][rel]],'Music files changed since installation; refusing overwrite.')
 plugin=game/PLUGIN
 p.check(not plugin.exists() or p.sha(plugin)==m['installed_hashes'][PLUGIN],'Plugin changed since installation; refusing removal.')
 for rel,h in profile['originals'].items():p.atomic_copy(backup/rel,game/rel);p.check(p.sha(game/rel)==h,'Restore verification failed.')
 if plugin.exists():plugin.unlink()
 target=game/'XtraTraxBackup.restored';n=1
 while target.exists():target=game/f'XtraTraxBackup.restored-{n}';n+=1
 backup.rename(target)
