"""Bounded float-to-MP3 encoding using the bundled source-built LAME library."""
from pathlib import Path
import ctypes as c
import hashlib,json,sys,tempfile,math
import numpy as np
import soundfile as sf

def library():
 root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))/'assets/encoder'
 path=root/'libmp3lame.dll';expected=json.loads((root/'runtime.json').read_text())
 if hashlib.sha256(path.read_bytes()).hexdigest()!=expected['dll_sha256']:
  raise ValueError('The bundled MP3 encoder is missing or damaged. Extract XtraTrax again.')
 dll=c.CDLL(str(path));dll.lame_init.restype=c.c_void_p
 return dll

def encode(path,dest,*,gain_db=0.0):
 dll=library();g=dll.lame_init()
 if not g:raise ValueError('Unable to initialize MP3 encoder.')
 def fn(name,args):
  f=getattr(dll,name);f.argtypes=args;f.restype=c.c_int;return f
 def check(result):
  if result<0:raise ValueError('MP3 encoding failed.')
  return result
 try:
  for name,value in [('in_samplerate',44100),('out_samplerate',44100),('num_channels',2),('brate',320),('quality',2),('bWriteVbrTag',0)]:
   check(fn('lame_set_'+name,[c.c_void_p,c.c_int])(g,value))
  check(fn('lame_init_params',[c.c_void_p])(g))
  encoder=fn('lame_encode_buffer_interleaved_ieee_float',[c.c_void_p,c.POINTER(c.c_float),c.c_int,c.POINTER(c.c_ubyte),c.c_int])
  buf=(c.c_ubyte*20000)();total=0
  with sf.SoundFile(str(path)) as source,Path(dest).open('wb') as out:
   if (source.samplerate,source.channels)!=(44100,2):raise ValueError('MP3 encoder requires prepared stereo audio.')
   while True:
    chunk=source.read(4096,dtype='float32',always_2d=True)
    if not len(chunk):break
    if not np.isfinite(chunk).all():raise ValueError('Audio contains invalid samples.')
    total+=len(chunk)
    if total>44100*60*30:raise ValueError('Track must be no longer than 30 minutes.')
    chunk=np.ascontiguousarray(chunk)
    if gain_db:chunk*=10**(gain_db/20)
    n=check(encoder(g,chunk.ctypes.data_as(c.POINTER(c.c_float)),len(chunk),buf,len(buf)));out.write(bytes(buf[:n]))
   if not total:raise ValueError('Track contains no audio.')
   n=check(fn('lame_encode_flush',[c.c_void_p,c.POINTER(c.c_ubyte),c.c_int])(g,buf,len(buf)));out.write(bytes(buf[:n]))
  return total
 finally:fn('lame_close',[c.c_void_p])(g)

def encode_protected(path,dest):
 """Measure the actual lossy result; always re-encode from prepared PCM."""
 import av
 import loudness
 expected=sf.info(str(path)).frames;gain=0.0
 with tempfile.TemporaryDirectory(prefix='XtraTrax-peak-') as tmp:
  decoded=Path(tmp)/'decoded.wav'
  for attempt in range(4):
   total=encode(path,dest,gain_db=gain)
   if total!=expected:raise ValueError('Input changed during encoding.')
   skip=1105;written=0
   with av.open(str(dest),options={'protocol_whitelist':'file'}) as source,sf.SoundFile(str(decoded),'w',samplerate=44100,channels=2,subtype='FLOAT') as out:
    for frame in source.decode(audio=0):
     a=frame.to_ndarray().T
     dropped=min(skip,len(a));skip-=dropped;a=a[dropped:]
     a=a[:max(0,total-written)]
     if len(a):out.write(a);written+=len(a)
   if written!=total:raise ValueError('Encoded track length could not be verified.')
   measured=loudness.measure(decoded)
   peak=measured['true_peak_dbtp']
   if peak<=loudness.CEILING_DBTP:
    clean=lambda v:v if math.isfinite(v) else None
    return total,dict(output_lufs=clean(measured['lufs']),output_true_peak_dbtp=clean(peak),post_encode_gain_db=gain)
   if not math.isfinite(peak):raise ValueError('Encoded peaks could not be measured.')
   gain-=peak-loudness.CEILING_DBTP+.05
 raise ValueError('Encoded track exceeds the protected peak ceiling.')
