"""Bounded float-to-MP3 encoding using the bundled source-built LAME library."""
from pathlib import Path
import ctypes as c
import hashlib,json,sys
import numpy as np
import soundfile as sf

def library():
 root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))/'assets/encoder'
 path=root/'libmp3lame.dll';expected=json.loads((root/'runtime.json').read_text())
 if hashlib.sha256(path.read_bytes()).hexdigest()!=expected['dll_sha256']:
  raise ValueError('The bundled MP3 encoder is missing or damaged. Extract XtraTrax again.')
 dll=c.CDLL(str(path));dll.lame_init.restype=c.c_void_p
 return dll

def encode(path,dest):
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
    n=check(encoder(g,chunk.ctypes.data_as(c.POINTER(c.c_float)),len(chunk),buf,len(buf)));out.write(bytes(buf[:n]))
   if not total:raise ValueError('Track contains no audio.')
   n=check(fn('lame_encode_flush',[c.c_void_p,c.POINTER(c.c_ubyte),c.c_int])(g,buf,len(buf)));out.write(bytes(buf[:n]))
  return total
 finally:fn('lame_close',[c.c_void_p])(g)
