"""Refuse a release build with different audio wheels or codec DLLs."""
from pathlib import Path
import hashlib, json

def verify():
    import av
    root=Path(__file__).resolve().parent
    expected=json.loads((root/'vendor/audio-runtime.json').read_text())
    wheel=root/'vendor'/expected['wheel']
    if hashlib.sha256(wheel.read_bytes()).hexdigest()!=expected['wheel_sha256']:
        raise RuntimeError('The bundled audio dependency wheel does not match its verified hash.')
    dll_dir=Path(av.__file__).resolve().parent.parent/'av.libs'
    actual={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in dll_dir.glob('*.dll')}
    if actual!=expected['dlls']:
        raise RuntimeError('This environment does not contain the verified audio-only runtime. Install requirements.txt from this Source directory first.')
    import soundfile
    snd=expected['soundfile']
    if hashlib.sha256((root/'vendor'/snd['wheel']).read_bytes()).hexdigest()!=snd['wheel_sha256']:
        raise RuntimeError('The SoundFile wheel does not match its verified hash.')
    dll=Path(soundfile.__file__).resolve().parent/'_soundfile_data/libsndfile_x64.dll'
    if hashlib.sha256(dll.read_bytes()).hexdigest()!=snd['dll_sha256']:
        raise RuntimeError('This environment does not contain the verified source-built libsndfile. Install requirements.txt first.')
    return expected

if __name__=='__main__':
    verify()
    print('Verified audio-only wheel and installed DLLs.')
