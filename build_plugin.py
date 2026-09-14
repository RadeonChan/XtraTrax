"""Build the checked-in archive runtime without regenerating validated source."""
from pathlib import Path
import sys,subprocess,json,re
import pefile
root=Path(__file__).resolve().parent
compiler=Path(sys.argv[1]);source=root/'plugin/NativeTrax.c';dll=root/'assets/NativeTrax.template'
subprocess.run([str(compiler),'-shared','-O2','-Wall','-Wextra','-Werror',str(source),'-ladvapi32','-Wl,--no-insert-timestamp','-o',str(dll)],check=True)
symbols={p[2]:int(p[0],16) for line in subprocess.check_output([str(compiler.parent/'llvm-nm.exe'),str(dll)],text=True).splitlines() if len(p:=line.split())==3}
pe=pefile.PE(str(dll));offset=lambda n:pe.get_offset_from_rva(symbols[n]-pe.OPTIONAL_HEADER.ImageBase)
capacity=int(re.search(r'#define TRACK_COUNT (\d+)',source.read_text()).group(1))-27
(root/'assets/template.json').write_text(json.dumps(dict(offset=offset('_packageConfig'),record_size=833,max_added=capacity,wide_banner_offset=offset('_forceWideBanners')),indent=2))
print('Built checked-in archive runtime with discovered offsets.')
