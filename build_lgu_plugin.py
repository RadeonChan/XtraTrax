"""Build the checked-in LGU x86 plugin and discover its configurable PE offsets."""
from pathlib import Path
import sys,subprocess,json,pefile,re
import lgu
root=Path(__file__).resolve().parent
# The gameplay logic is shared. Only the verified address/file-layout profile differs.
us_loose='--us-loose' in sys.argv
profile=lgu.PROFILES['magipack-loose' if us_loose else 'lgu-loose']
source=root/'plugin'/profile['assets'];source.mkdir(exist_ok=True)
if us_loose:
 import shutil
 shutil.copy2(root/'plugin/patches.h',source/'patches.h')
mapping={} if us_loose else {int(k,16):int(v,16) for k,v in json.loads((source/'address-map.json').read_text()).items()}
s=(root/'plugin/NativeTrax.c').read_text(encoding='utf-8')
s=re.sub(r'0x[0-9a-fA-F]+',lambda x:hex(mapping.get(int(x[0],16),int(x[0],16))),s)
digest=','.join('0x'+profile['exe_sha256'][i:i+2] for i in range(0,64,2))
s,n=re.subn(r'static const BYTE exeHash\[32\]=\{[^}]+\}','static const BYTE exeHash[32]={'+digest+'}',s);assert n==1
s=s.replace('slash-path+16>=MAX_PATH','slash-path+32>=MAX_PATH')
old=r'strcpy(slash+1,"SDATA\\sdat.viv");return verifyHash(path,packageConfig.archive);'
new='strcpy(slash+1,"PFDATA\\\\MusicSFx.mus");if(!verifyHash(path,packageConfig.archive))return 0;\n strcpy(slash+1,"PFDATA\\\\MusicSFx.mpf");return verifyHash(path,lguMapHash);'
assert old in s;s=s.replace(old,new)
s=s.replace('static int verifyFiles(void)','__declspec(dllexport) BYTE lguMapHash[32]={0x4c,0x47,0x55,0xff};\nstatic int verifyFiles(void)')
suffix='MagiPack' if us_loose else 'LGU'
s=s.replace('NativeTrax.log','NativeTrax-'+suffix+'.log').replace('NFSU2-NativeTrax.ini','NFSU2-NativeTrax-'+suffix+'.ini')
if us_loose:
 # The longer MagiPack filename exceeds the shared 18-byte allowance.
 # Include its NUL terminator while preserving the other validated profiles.
 s=s.replace('tempLen+18<MAX_PATH','tempLen+sizeof("NativeTrax-MagiPack.log")<=MAX_PATH')
(source/'NativeTrax.c').write_text(s,encoding='utf-8')
compiler=Path(sys.argv[1]);out=root/'assets'/profile['assets'];out.mkdir(exist_ok=True);dll=out/'NativeTrax.template'
subprocess.run([str(compiler),'-shared','-O2','-Wall','-Wextra','-Werror',str(source/'NativeTrax.c'),'-ladvapi32','-Wl,--no-insert-timestamp','-o',str(dll)],check=True)
symbols={a[2]:int(a[0],16) for line in subprocess.check_output([str(compiler.parent/'llvm-nm.exe'),str(dll)],text=True).splitlines() if len(a:=line.split())==3}
p=pefile.PE(str(dll));offset=lambda n:p.get_offset_from_rva(symbols[n]-p.OPTIONAL_HEADER.ImageBase)
(out/'template.json').write_text(json.dumps(dict(offset=offset('_packageConfig'),record_size=833,max_added=100,wide_banner_offset=offset('_forceWideBanners'),map_hash_offset=offset('_lguMapHash')),indent=2))
print('LGU template built with discovered offsets.')
