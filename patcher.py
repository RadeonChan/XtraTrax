"""Native Trax alpha: exact-build local archive builder and reversible installer."""
from pathlib import Path
import hashlib,json,struct,shutil,tempfile,subprocess,os,sys
import lgu
import numpy as np
import soundfile as sf
import audio_input
import loudness
import diagnostics

REQUIRED_GAME_VERSION='US v1.2'
MAX_ADDED=100
MAX_SOUNDTRACK_BYTES=0x80000000
EXE_SHA='f9dd86c054878ce6276beb07c1fd61874f7a1e4bf1f241b084c65b73e2'+'4168a7'
ORIGINAL_SHA='379a3cd7c16a5090590248616042f8af3ac0c234a58dc9f58c7eee200377e3f1'
ASSETS=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))/'assets'
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  while b:=f.read(1048576):h.update(b)
 return h.hexdigest()
def check(condition,message):
 if not condition:raise ValueError(message)
def align(n,a=4):return (n+a-1)//a*a

def check_soundtrack_size(size):
 check(size<MAX_SOUNDTRACK_BYTES,
       'This playlist is too long to fit the supported soundtrack size. '
       'Remove some songs or choose shorter tracks, then try again. '
       'The limit is 2 GiB after audio conversion, including the original soundtrack.')
def field(k,v):
 z=v.to_bytes(max(1,(v.bit_length()+7)//8),'big')
 if z[0]&128:z=b'\0'+z
 return bytes([k,len(z)])+z
def block(tag,payload):
 payload+=b'\0'*((-len(payload))%4)
 return tag+struct.pack('<I',8+len(payload))+payload
def text_bytes(value):
 check(isinstance(value,str) and '\0' not in value,'Metadata must be text without NUL characters.')
 b=value.encode('utf-8');check(len(b)<=255,'Each text field is limited to 255 UTF-8 bytes.')
 return b+b'\0'*(256-len(b))
def inspect_audio(path):
 return audio_input.inspect(path)

def encode(track,dest):
 check(type(track.get('normalize',False)) is bool,'Volume matching must be enabled or disabled.')
 with audio_input.prepared(track['path'],floating=track.get('normalize',False)) as path:
  if track.get('normalize',False):
   with tempfile.TemporaryDirectory(prefix='XtraTrax-volume-') as tmp:
    matched=Path(tmp)/'matched.wav';report=(loudness.match_limited if track.get('limiting',False) else loudness.match)(path,matched)
    result=encode_pcm(dict(track,path=str(matched)),dest);result['normalization']=report
    return result
  return encode_pcm(dict(track,path=str(path)),dest)

def encode_pcm(track,dest):
 path=Path(track['path']);info=sf.info(str(path))
 for k in ['title','artist','album']:text_bytes(track[k])
 check(track['title'].strip(),'Title cannot be blank.')
 frames=info.frames;h=hashlib.sha256()
 header=b'PT\0\0'+bytes.fromhex('06 01 65 0b 01 02 fd')
 header+=b''.join(field(k,v) for k,v in [(0x80,2),(0x85,frames),(0x82,2),(0x84,44100),(0xa0,8)])+b'\xff'
 with sf.SoundFile(str(path)) as inp,Path(dest).open('wb') as out:
  out.write(block(b'SCHl',header));out.write(block(b'SCCl',struct.pack('<I',(frames+511)//512)))
  total=0
  while len(pcm:=inp.read(512,dtype='int16',always_2d=True)):
   pcm=pcm.astype('<i2',copy=False);h.update(pcm.tobytes());n=len(pcm);total+=n
   left=pcm[:,0].tobytes();out.write(block(b'SCDl',struct.pack('<III',n,0,len(left))+left+pcm[:,1].tobytes()))
  check(total==frames,'Input changed during encoding.');out.write(block(b'SCEl',b''))
 return dict(title=track['title'],artist=track['artist'],album=track['album'],frames=frames,key=h.hexdigest(),stream=str(dest))
def directory(path):
 with Path(path).open('rb') as f:
  b=f.read(4096);check(b[:4]==b'BIG4','Not a BIG4 archive.');pos=16;result=[]
  for _ in range(struct.unpack_from('>I',b,8)[0]):
   offset,size=struct.unpack_from('>II',b,pos);pos+=8;end=b.index(b'\0',pos);result.append((b[pos:end].decode(),offset,size));pos=end+1
 return result
def copyrange(inp,out,offset,size):
 inp.seek(offset)
 while size:
  b=inp.read(min(size,1048576));check(bool(b),'Unexpected end of archive.');out.write(b);size-=len(b)
def detect_game(game):
 """Recognize executable and audio layout independently; never infer layout from EXE."""
 path=Path(game).resolve();actual=sha(path/'SPEED2.EXE')
 labels={EXE_SHA:'Underground 2 US v1.2',lgu.EXE_SHA:'Underground 2 — verified LGU executable'}
 label=labels.get(actual,'Unsupported executable');target='unsupported';layout='No matching verified build';supported=False
 if actual in labels:
  if lgu.is_loose(path):
   profile=lgu.profile_for(path);target=profile['target'];layout=profile['name']+' loose music layout'
   try:
    check(not (path/'SDATA/sdat.viv').exists(),'Mixed active audio layouts')
    expected=profile['originals']
    receipt=path/'XtraTraxBackup/receipt.json'
    if receipt.exists():
     m=json.loads(receipt.read_text(encoding='utf-8'));lgu.validate_manifest(m,profile);expected={rel:m['installed_hashes'][rel] for rel in profile['originals']}
    supported=all(sha(path/rel)==h for rel,h in expected.items())
   except (OSError,ValueError,KeyError):supported=False
   if not supported:layout='Unverified or mixed loose music files'
  else:
   target='us-archive' if actual==EXE_SHA else 'unsupported';layout='Original archive layout'
   supported=target=='us-archive' and (path/'SDATA/sdat.viv').is_file()
 return dict(target=target,label=label,layout=layout,exe_sha256=actual,supported=supported)

def validate_game(game,original=True):
 game=Path(game).resolve();actual=sha(game/'SPEED2.EXE')
 check(actual in [EXE_SHA,lgu.EXE_SHA],f'Unsupported SPEED2.EXE SHA256: {actual}. A version label alone does not establish compatibility.')
 if lgu.is_loose(game):
  if original:lgu.validate_original(game)
  return game
 check(actual==EXE_SHA,'This executable requires its verified loose music layout.')
 if original:check(sha(game/'SDATA/sdat.viv')==ORIGINAL_SHA,'Restore the original supported sdat.viv first; modified archives are not merged.')
 return game

def make_plugin(records,archive_hash,wide_banners=False,*,map_hash=None,template_profile=None):
 assets=ASSETS/(template_profile or 'lgu') if map_hash is not None else ASSETS
 data=bytearray((assets/'NativeTrax.template').read_bytes());layout=json.loads((assets/'template.json').read_text());offset=layout['offset'];check(1<=len(records)<=min(MAX_ADDED,layout['max_added']),'Track count exceeds runtime allocation.')
 if map_hash is not None:data[layout['map_hash_offset']:layout['map_hash_offset']+32]=bytes.fromhex(map_hash)
 check(type(wide_banners) is bool,'Wide-banner option must be boolean.')
 struct.pack_into('<I',data,layout['wide_banner_offset'],int(wide_banners))
 check(data[offset:offset+15]==b'NATIVE_TRAX_V1\0','Invalid plugin template.')
 struct.pack_into('<I',data,offset+16,len(records));data[offset+20:offset+52]=bytes.fromhex(archive_hash)
 for i,r in enumerate(records):
  entry=b''.join(text_bytes(r[k]) for k in ['title','artist','album'])+r['key'].encode()+b'\0'
  check(len(entry)==833,'Invalid record layout.');start=offset+52+i*833;data[start:start+833]=entry
 return data
def expand_music(m,stream_path,stream_offset,stream_size,records,temp,*,relocate_last=False):
 check(len(m)==6840,'Unexpected Pathfinder map.')
 u16=lambda off:struct.unpack_from('<H',m,off)[0]
 no=[u16(32+i*2)*4 for i in range(162)];eo=[u16(0xd34+i*2)*4 for i in range(79)]
 nodes=[m[o:no[i+1] if i<161 else 0xd34] for i,o in enumerate(no)];events=[m[o:eo[i+1] if i<78 else 0x1954] for i,o in enumerate(eo)]
 samples=bytearray(m[0x1960:0x1ab8]);mus=temp/'MusicSFx.mus'
 projected=stream_size
 if relocate_last:
  last=struct.unpack_from('<I',samples,42*8)[0]*128
  next_offset=min(o*128 for o,t in struct.iter_unpack('<II',samples) if o*128>last)
  projected+=next_offset-last
 for r in records:projected=align(align(projected,128)+Path(r['stream']).stat().st_size,128)
 check_soundtrack_size(projected)
 with Path(stream_path).open('rb') as inp,mus.open('wb') as out:
  copyrange(inp,out,stream_offset,stream_size)
  if relocate_last:
   last=struct.unpack_from('<I',samples,42*8)[0]*128
   next_offset=min(o*128 for o,t in struct.iter_unpack('<II',samples) if o*128>last)
   check(out.tell()%128==0,'Unaligned original audio stream.')
   struct.pack_into('<I',samples,42*8,out.tell()//128)
   copyrange(inp,out,stream_offset+last,next_offset-last)
  for j,r in enumerate(records):
   off=align(out.tell(),128);out.write(b'\0'*(off-out.tell()))
   with Path(r['stream']).open('rb') as f:shutil.copyfileobj(f,out)
   out.write(b'\0'*(align(out.tell(),128)-out.tell()))
   node=162+3*j;event=79+j;sample=44+j;extra=[bytearray(x) for x in nodes[:3]]
   struct.pack_into('<H',extra[0],18,node+2);struct.pack_into('<H',extra[2],18,node+1);struct.pack_into('<H',extra[2],0,sample);nodes.extend(bytes(x) for x in extra)
   ev=bytearray(events[0]);struct.pack_into('<H',ev,12,event);struct.pack_into('<H',ev,0x1c,node);events.append(bytes(ev))
   samples+=struct.pack('<II',off//128,round(r['frames']*1000/44100));r.update(row=28+j,event=event,sample=sample,offset=off)
 mpf=bytearray(m[:32]);struct.pack_into('<H',mpf,0x12,len(nodes));mpf[15]=len(events);mpf+=b'\0'*(align(32+len(nodes)*2)-32)
 for i,n in enumerate(nodes):struct.pack_into('<H',mpf,32+i*2,len(mpf)//4);mpf+=n
 et=len(mpf);mpf+=b'\0'*align(len(events)*2)
 for i,e in enumerate(events):struct.pack_into('<H',mpf,et+i*2,len(mpf)//4);mpf+=e
 tt=len(mpf)+4;st=tt+8;mpf+=struct.pack('<III',tt//4,st//4,(st+len(samples))//4)+samples
 # Original map contents must survive relocation exactly.
 for i,n in enumerate(nodes[:162]):
  o=struct.unpack_from('<H',mpf,32+i*2)[0]*4;check(mpf[o:o+len(n)]==n,'Original node changed.')
 for i,e in enumerate(events[:79]):
  o=struct.unpack_from('<H',mpf,et+i*2)[0]*4;check(mpf[o:o+len(e)]==e,'Original event changed.')
 (temp/'MusicSFx.mpf').write_bytes(mpf)
 return mus

def build(game,tracks,output,progress=lambda s:None,*,wide_banners=False):
 game=validate_game(game)
 if lgu.is_loose(game):return lgu.build(game,tracks,output,progress,wide_banners=wide_banners)
 output=Path(output).resolve()
 check(1<=len(tracks)<=MAX_ADDED,'Add between 1 and 100 tracks (28–127 total).')
 check(not output.exists(),'Choose a new, empty output folder name.')
 check(not output.is_relative_to(game),'Build outside the game folder.')
 # Validate the complete queue before creating output or encoding.
 for t in tracks:
  inspect_audio(t['path'])
  for k in ['title','artist','album']:text_bytes(t[k])
 output.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='native-trax-',dir=output.parent) as temp:
  temp=Path(temp);records=[]
  minimum_size=(game/'SDATA/sdat.viv').stat().st_size
  for i,t in enumerate(tracks):
   progress(f'Encoding {i+1}/{len(tracks)}: {t["title"]}');records.append(encode(t,temp/f'{i}.asf'))
   minimum_size+=(temp/f'{i}.asf').stat().st_size;check_soundtrack_size(minimum_size)
  check(len({r['key'] for r in records})==len(records),'Duplicate audio in the queue. Keep one copy so preferences remain unambiguous.')
  archive=game/'SDATA/sdat.viv';entries=directory(archive);lookup={n:(o,z) for n,o,z in entries}
  with archive.open('rb') as f:f.seek(lookup['pfdata/MusicSFx.mpf'][0]);m=f.read(lookup['pfdata/MusicSFx.mpf'][1])
  mus=expand_music(m,archive,*lookup['pfdata/MusicSFx.mus'],records,temp)
  header_size=16+sum(9+len(n.encode()) for n,_,_ in entries);offset=align(header_size,64);parts=[];d=bytearray()
  for n,o,z in entries:
   replacement=mus if n.endswith('MusicSFx.mus') else temp/'MusicSFx.mpf' if n.endswith('MusicSFx.mpf') else None
   size=replacement.stat().st_size if replacement else z
   next_offset=align(offset+size,64);check_soundtrack_size(next_offset)
   d+=struct.pack('>II',offset,size)+n.encode()+b'\0';parts.append((offset,replacement,o,size));offset=next_offset
  stage=temp/'result';(stage/'SDATA').mkdir(parents=True);(stage/'SCRIPTS').mkdir()
  progress('Building and hashing the local archive…')
  with archive.open('rb') as inp,(stage/'SDATA/sdat.viv').open('wb') as out:
   out.write(b'BIG4'+struct.pack('>III',offset,len(entries),align(header_size,64))+d)
   for off,replacement,o,size in parts:
    out.write(b'\0'*(off-out.tell()))
    if replacement:
     with replacement.open('rb') as f:shutil.copyfileobj(f,out)
    else:copyrange(inp,out,o,size)
   out.write(b'\0'*(offset-out.tell()))
  archive_hash=sha(stage/'SDATA/sdat.viv');(stage/'SCRIPTS/NativeTrax.asi').write_bytes(make_plugin(records,archive_hash,wide_banners))
  for r in records:r.pop('stream')
  manifest=dict(version=1,wide_banners=wide_banners,exe_sha256=EXE_SHA,original_sha256=ORIGINAL_SHA,archive_sha256=archive_hash,plugin_sha256=sha(stage/'SCRIPTS/NativeTrax.asi'),records=records)
  (stage/'native-trax.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
  shutil.move(str(stage),str(output))
 return manifest
def require_closed():
 flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
 p=subprocess.run(['tasklist','/FI','IMAGENAME eq SPEED2.EXE','/FO','CSV','/NH'],capture_output=True,text=True,creationflags=flags)
 check(p.returncode==0,'Unable to check running processes.')
 check('speed2.exe' not in p.stdout.lower(),'Close Underground 2 before installing or restoring.')
def atomic_copy(src,dest):
 dest=Path(dest);dest.parent.mkdir(parents=True,exist_ok=True)
 fd,tmp=tempfile.mkstemp(prefix='.native-trax-',dir=dest.parent);os.close(fd)
 try:
  expected=sha(src);shutil.copyfile(src,tmp)
  copied=sha(tmp);after=sha(src)
  if copied!=expected or after!=expected:
   error=ValueError('Staged file copy failed verification; destination unchanged.')
   detail=dict(source=diagnostics.file_state(src),destination=diagnostics.file_state(dest),staged=diagnostics.file_state(tmp),expected=expected,copied=copied,source_after=after)
   try:
    detail.update(temp_again=sha(tmp),source_again=sha(src))
    with Path(src).open('rb') as a,Path(tmp).open('rb') as b:
     offset=0
     while chunk:=a.read(1048576):
      other=b.read(len(chunk))
      if chunk!=other:
       detail['first_difference']=offset+next((i for i,(x,y) in enumerate(zip(chunk,other)) if x!=y),min(len(chunk),len(other)));break
      offset+=len(chunk)
   except Exception as inspection_error:detail['inspection_error']=str(inspection_error)
   diagnostics.save(error,'verify staged copy',detail)
   # Retain the explicit test hook; never let report writing mask the refusal.
   diagnostic=os.environ.get('XTRATRAX_COPY_DIAGNOSTIC')
   if diagnostic:
    try:Path(diagnostic).write_text(json.dumps(detail,indent=2),encoding='utf-8')
    except OSError:pass
   raise error
  os.replace(tmp,dest)
 finally:
  if Path(tmp).exists():Path(tmp).unlink()
def prepare_backup(game,originals,manifest):
 """Publish a complete verified backup; failed preparation never claims installation."""
 game=Path(game);backup=game/'XtraTraxBackup'
 check(not backup.exists(),'A XtraTraxBackup already exists. Restore it first.')
 with tempfile.TemporaryDirectory(prefix='.native-trax-backup-pending-',dir=game) as pending:
  staged=Path(pending)
  for rel,(saved,digest) in originals.items():
   dest=staged/saved;dest.parent.mkdir(parents=True,exist_ok=True)
   shutil.copyfile(game/rel,dest)
   check(sha(dest)==digest,'Backup verification failed; game unchanged.')
  receipt=staged/'receipt.json'
  receipt.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
  check(json.loads(receipt.read_text(encoding='utf-8'))==manifest,'Backup receipt verification failed; game unchanged.')
  check(not backup.exists(),'A XtraTraxBackup appeared during preparation; game unchanged.')
  staged.rename(backup)

def install(game,package):
 require_closed();game=validate_game(game)
 if lgu.is_loose(game):return lgu.install(game,package)
 package=Path(package);m=json.loads((package/'native-trax.json').read_text())
 check(m['exe_sha256']==EXE_SHA and m['original_sha256']==ORIGINAL_SHA,'Unsupported package version/build.')
 check(sha(package/'SDATA/sdat.viv')==m['archive_sha256'] and sha(package/'SCRIPTS/NativeTrax.asi')==m['plugin_sha256'],'Package failed integrity check.')
 check((game/'dinput8.dll').is_file(),'This alpha requires an existing dinput8 ASI loader. Install/configure your loader separately.')
 check(not (game/'SCRIPTS/Trax28.asi').exists() and not (game/'SCRIPTS/NativeTrax.asi').exists(),'An existing soundtrack plugin is present. Restore/remove it before installing this alpha.')
 prepare_backup(game,{'SDATA/sdat.viv':('sdat.viv',ORIGINAL_SHA)},m)
 try:
  atomic_copy(package/'SDATA/sdat.viv',game/'SDATA/sdat.viv');atomic_copy(package/'SCRIPTS/NativeTrax.asi',game/'SCRIPTS/NativeTrax.asi')
  check(sha(game/'SDATA/sdat.viv')==m['archive_sha256'] and sha(game/'SCRIPTS/NativeTrax.asi')==m['plugin_sha256'],'Installed verification failed.')
 except Exception:
  restore(game);raise
def restore(game):
 require_closed();game=validate_game(game,False)
 if lgu.is_loose(game):return lgu.restore(game)
 backup=game/'XtraTraxBackup';m=json.loads((backup/'receipt.json').read_text())
 check(sha(backup/'sdat.viv')==ORIGINAL_SHA,'Backup failed verification.')
 check(sha(game/'SDATA/sdat.viv') in [ORIGINAL_SHA,m['archive_sha256']],'Game archive changed since installation; refusing to overwrite it.')
 plugin=game/'SCRIPTS/NativeTrax.asi'
 check(not plugin.exists() or sha(plugin)==m['plugin_sha256'],'Plugin changed since installation; refusing to remove it.')
 atomic_copy(backup/'sdat.viv',game/'SDATA/sdat.viv')
 if plugin.exists():plugin.unlink()
 # Keep backup for recovery, rename it so a subsequent install can proceed.
 target=game/'XtraTraxBackup.restored';n=1
 while target.exists():target=game/f'XtraTraxBackup.restored-{n}';n+=1
 backup.rename(target)

