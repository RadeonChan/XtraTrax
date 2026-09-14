"""Local audio input conversion. No normalization, ReplayGain or gain filters."""
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import tempfile
import av
import numpy as np
import soundfile as sf

EXTENSIONS=('.wav','.flac','.m4a','.mp3','.ogg')
MAX_FRAMES=44100*60*30

def inspect(path):
 path=Path(path)
 if path.suffix.lower() not in EXTENSIONS:
  raise ValueError('Supported inputs: WAV, FLAC, M4A, MP3 or Ogg.')
 try:
  with av.open(str(path),options={'protocol_whitelist':'file'}) as source:
   if len(source.streams.audio)!=1:raise ValueError('Choose a file containing exactly one audio track.')
   stream=source.streams.audio[0];ctx=stream.codec_context
   if ctx.channels not in (1,2):raise ValueError('Only mono or stereo audio is supported.')
   if not ctx.sample_rate:raise ValueError('Unable to determine the audio sample rate.')
   allowed={'.m4a':{'aac','alac'},'.mp3':{'mp3','mp3float'},'.ogg':{'vorbis','opus'}}
   if path.suffix.lower() in allowed and ctx.name not in allowed[path.suffix.lower()]:
    raise ValueError('Unsupported codec inside this audio file.')
   duration=float(stream.duration*stream.time_base) if stream.duration is not None else None
   if duration is not None and not 0<duration<=1800:raise ValueError('Track must contain audio and be no longer than 30 minutes.')
   return SimpleNamespace(frames=round(duration*ctx.sample_rate) if duration else None,samplerate=ctx.sample_rate,channels=ctx.channels)
 except av.FFmpegError as e:
  raise ValueError(f'{path.name}: unable to read audio; the file may be damaged or protected.') from e

@contextmanager
def prepared(path, *, floating=False):
 """Keep supported original PCM byte-exact; otherwise decode to bounded temp PCM."""
 path=Path(path);inspect(path)
 if path.suffix.lower() in ('.wav','.flac'):
  info=sf.info(str(path))
  if (info.samplerate,info.channels,info.subtype)==(44100,2,'PCM_16'):
   if not 0<info.frames<=MAX_FRAMES:raise ValueError('Track must contain audio and be no longer than 30 minutes.')
   yield path;return
 with tempfile.TemporaryDirectory(prefix='XtraTrax-audio-') as tmp:
  output=Path(tmp)/'converted.wav';total=0
  try:
   with av.open(str(path),options={'protocol_whitelist':'file'}) as source,sf.SoundFile(str(output),'w',samplerate=44100,channels=2,subtype='FLOAT' if floating else 'PCM_16') as dest:
    stream=source.streams.audio[0];channels=stream.codec_context.channels
    converter=av.AudioResampler(format='flt' if floating else 's16',layout='mono' if channels==1 else 'stereo',rate=44100)
    def write(frame):
     nonlocal total
     pcm=frame.to_ndarray().reshape(-1,channels)
     if channels==1:pcm=np.repeat(pcm,2,axis=1)
     total+=len(pcm)
     if total>MAX_FRAMES:raise ValueError('Track must be no longer than 30 minutes.')
     dest.write(pcm)
    for frame in source.decode(stream):
     frame.pts=None
     for converted in converter.resample(frame):write(converted)
    for converted in converter.resample(None):write(converted)
   if not total:raise ValueError('Track contains no decodable audio.')
  except av.FFmpegError as e:
   raise ValueError(f'{path.name}: audio conversion failed; the file may be damaged or protected.') from e
  yield output
