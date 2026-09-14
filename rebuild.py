"""Portable frontend rebuild from the supplied Source directory.
Run: python rebuild.py
Requires requirements.txt. Reuses the shipped, tested plugin template.
"""
from pathlib import Path
import subprocess,sys,shutil,os
from diagnostics import VERSION
from dependency_runtime import verify
root=Path(__file__).resolve().parent
verify()
if not (root/'assets').exists():shutil.copytree(root.parent/'_internal/assets',root/'assets')
env=os.environ.copy()
base=Path(sys.base_prefix)
windows=Path(os.environ.get('SystemRoot',r'C:\Windows'))
env['PATH']=os.pathsep.join(str(p) for p in [Path(sys.executable).parent,base/'Library/bin',base/'DLLs',base,windows/'System32',windows] if p.is_dir())
subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--windowed','--onedir','--name','XtraTrax','--icon',str(root/'assets/XtraTrax.ico'),'--distpath',str(root/('dist-'+VERSION)),'--workpath',str(root/('freeze-work-'+VERSION)),'--specpath',str(root),'--add-data',str(root/'assets')+';assets',str(root/'app.py')],check=True,env=env)
