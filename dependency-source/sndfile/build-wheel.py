from pathlib import Path
import os,subprocess,sys,shutil
root=Path(__file__).resolve().parent
source=root/'python-soundfile'
if not source.exists():
    # Source checkout is pinned by the audit; no binary submodule is copied.
    shutil.copytree(root.parent/'XtraTrax-Final-Review/python-soundfile',source,
        ignore=shutil.ignore_patterns('.git','_soundfile_data','__pycache__'))
data=source/'_soundfile_data';data.mkdir(exist_ok=True)
(data/'__init__.py').write_text('')
shutil.copy2(root/'prefix/bin/libsndfile.dll',data/'libsndfile_x64.dll')
shutil.copy2(root/'libsndfile/COPYING',data/'COPYING')
notes=['# XtraTrax source-built libsndfile dependency\n',
    'libsndfile 1.2.2 (LGPL 2.1-or-later) is linked with the pinned Xiph libraries below. MPEG support is disabled. Full corresponding sources and build recipes accompany the XtraTrax distribution. python-soundfile 0.14.0 remains BSD-3-Clause.\n']
for name,version,notice in [('ogg','1.3.5','COPYING'),('flac','1.4.3','COPYING.Xiph'),('vorbis','1.3.7','COPYING'),('opus','1.5.2','COPYING')]:
    notes.append('\n## '+name+' '+version+'\n\n'+(root/name/notice).read_text(encoding='utf-8'))
(source/'licensing/license_notes.md').write_text('\n'.join(notes),encoding='utf-8')
env=os.environ.copy();env['PYSOUNDFILE_PLATFORM']='win32';env['PYSOUNDFILE_ARCHITECTURE']='x64'
subprocess.run([sys.executable,'setup.py','bdist_wheel'],cwd=source,env=env,check=True)
