"""Gain-only loudness matching. FFmpeg loudnorm is used ONLY as a meter."""
from pathlib import Path
import json,math
import av,numpy as np,soundfile as sf

TARGET_LUFS=-9.0  # Product target, rounded from measured original references (~ -8.6).
CEILING_DBTP=-1.0

def measure(path):
 graph=av.filter.Graph()
 with sf.SoundFile(str(path)) as inp:
  source=graph.add_abuffer(sample_rate=inp.samplerate,format='fltp',layout='stereo')
  meter=graph.add('loudnorm','I=-9:TP=-1:print_format=json')
  sink=graph.add('abuffersink');source.link_to(meter);meter.link_to(sink);graph.configure()
  def drain():
   while True:
    try:sink.pull()  # Discard all processed audio; only input measurements matter.
    except (av.error.BlockingIOError,av.error.EOFError):return
  previous=av.logging.get_level();repeated=av.logging.get_skip_repeated();av.logging.set_skip_repeated(False);av.logging.set_level(av.logging.INFO)
  try:
   with av.logging.Capture() as logs:
    for pcm in inp.blocks(blocksize=16384,dtype='float32',always_2d=True):
     if not np.isfinite(pcm).all():raise ValueError('Audio contains non-finite samples.')
     if pcm.shape[1]!=2:raise ValueError('Loudness measurement requires stereo PCM.')
     frame=av.AudioFrame.from_ndarray(pcm.T.copy(),format='fltp',layout='stereo');frame.sample_rate=inp.samplerate
     source.push(frame);drain()
    source.push(None);drain()
    del source,meter,sink,graph
   reports=[json.loads(text) for _,name,text in logs if name=='loudnorm' and '"input_i"' in text]
   if not reports:raise ValueError('Unable to measure track loudness.')
   return dict(lufs=float(reports[-1]['input_i']),true_peak_dbtp=float(reports[-1]['input_tp']))
  finally:av.logging.set_level(previous);av.logging.set_skip_repeated(repeated)

def match(path,dest):
 before=measure(path);loudness=before['lufs'];peak=before['true_peak_dbtp']
 # Meter output is rounded to .01 dB; reserve a small measurement/quantization margin.
 gain=min(TARGET_LUFS-loudness,CEILING_DBTP-.05-peak) if math.isfinite(loudness) and math.isfinite(peak) else min(0,CEILING_DBTP-.05-peak) if math.isfinite(peak) else 0
 def render():
  with sf.SoundFile(str(path)) as inp,sf.SoundFile(str(dest),'w',samplerate=inp.samplerate,channels=2,subtype='PCM_16') as out:
   for pcm in inp.blocks(blocksize=16384,dtype='float64',always_2d=True):out.write(pcm*10**(gain/20))
 render();after=measure(dest)
 if math.isfinite(after['true_peak_dbtp']) and after['true_peak_dbtp']>CEILING_DBTP:
  gain-=after['true_peak_dbtp']-CEILING_DBTP+.05;render();after=measure(dest)
 if after['true_peak_dbtp']>CEILING_DBTP:raise ValueError('Converted track exceeds the protected peak ceiling.')
 clean=lambda x:x if math.isfinite(x) else None
 return dict(target_lufs=TARGET_LUFS,ceiling_dbtp=CEILING_DBTP,gain_db=gain,input_lufs=clean(loudness),output_lufs=clean(after['lufs']),output_true_peak_dbtp=clean(after['true_peak_dbtp']),peak_constrained=math.isfinite(loudness) and gain<TARGET_LUFS-loudness-.1)

def render_limited(path,dest,gain_db):
 """Oversampled lookahead limiting with automatic makeup gain disabled."""
 with sf.SoundFile(str(path)) as inp,sf.SoundFile(str(dest),'w',samplerate=44100,channels=2,subtype='PCM_16') as out:
  graph=av.filter.Graph();source=graph.add_abuffer(sample_rate=inp.samplerate,format='fltp',layout='stereo')
  nodes=[source,graph.add('aresample','192000'),graph.add('volume',f'{gain_db}dB'),graph.add('alimiter',f'limit={10**(-1.2/20)}:attack=5:release=50:level=0:latency=1'),graph.add('aresample','44100'),graph.add('aformat','sample_fmts=flt:channel_layouts=stereo'),graph.add('abuffersink')]
  for a,b in zip(nodes,nodes[1:]):a.link_to(b)
  graph.configure();total=0
  def drain():
   nonlocal total
   while True:
    try:frame=nodes[-1].pull()
    except (av.error.BlockingIOError,av.error.EOFError):return
    pcm=frame.to_ndarray().reshape(-1,2);out.write(pcm);total+=len(pcm)
  for pcm in inp.blocks(blocksize=16384,dtype='float32',always_2d=True):
   frame=av.AudioFrame.from_ndarray(pcm.T.copy(),format='fltp',layout='stereo');frame.sample_rate=inp.samplerate;source.push(frame);drain()
  source.push(None);drain()
  if total!=inp.frames:raise ValueError('Limiter changed track length; output refused.')

def match_limited(path,dest):
 before=measure(path)
 if not math.isfinite(before['lufs']):
  report=match(path,dest);report['mode']='limiting';return report
 gain=TARGET_LUFS-before['lufs']
 for attempt in range(4):
  render_limited(path,dest,gain);after=measure(dest)
  error=TARGET_LUFS-after['lufs']
  if abs(error)<=.2 or attempt==3:break
  gain+=max(-3,min(3,error))
 # Reconstructed peaks can overshoot slightly after downsampling. Protect the
 # final PCM rather than trusting the limiter's internal sample ceiling.
 correction=0
 if after['true_peak_dbtp']>CEILING_DBTP:
  correction=CEILING_DBTP-.05-after['true_peak_dbtp']
  with sf.SoundFile(str(dest),'r+') as out:
   offset=0
   while offset<len(out):
    out.seek(offset);pcm=out.read(16384,dtype='float64',always_2d=True)
    out.seek(offset);out.write(pcm*10**(correction/20));offset+=len(pcm)
  after=measure(dest)
 if after['true_peak_dbtp']>CEILING_DBTP:raise ValueError('Limited output exceeds the protected peak ceiling.')
 return dict(mode='limiting',target_lufs=TARGET_LUFS,ceiling_dbtp=CEILING_DBTP,gain_db=gain,input_lufs=before['lufs'],output_lufs=after['lufs'],output_true_peak_dbtp=after['true_peak_dbtp'],post_gain_db=correction,target_reached=abs(after['lufs']-TARGET_LUFS)<=.25)
