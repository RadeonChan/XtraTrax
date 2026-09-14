"""Build the pinned encoder-only LAME DLL with x64 LLVM-MinGW."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys,tarfile,tempfile
root=Path(__file__).resolve().parent
meta=json.loads((root/'provenance.json').read_text());archive=root/'lame-3.100.tar.gz'
if hashlib.sha256(archive.read_bytes()).hexdigest()!=meta['source_sha256']:raise RuntimeError('LAME source hash mismatch.')
compiler=Path(sys.argv[1]).resolve();output=root.parents[1]/'assets/encoder/libmp3lame.dll'
with tempfile.TemporaryDirectory(prefix='XtraTrax-LAME-') as tmp:
 with tarfile.open(archive) as tar:tar.extractall(tmp,filter='data')
 source=Path(tmp)/'lame-3.100';shutil.copy2(root/'config.h',source/'config.h')
 files=[str(p) for p in sorted((source/'libmp3lame').glob('*.c'))]
 subprocess.run([str(compiler),'-shared','-O2','-DHAVE_CONFIG_H','-ffile-prefix-map='+str(source)+'=/lame','-I'+str(source),'-I'+str(source/'include'),'-I'+str(source/'libmp3lame'),*files,'-Wl,--no-insert-timestamp','-Wl,--export-all-symbols','-o',str(output)],check=True)
print('Encoder SHA256:',hashlib.sha256(output.read_bytes()).hexdigest())
