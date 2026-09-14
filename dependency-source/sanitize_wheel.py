"""Remove local build-directory prefixes from wheel metadata and DLL strings.

This changes diagnostic/configuration strings only. PE executable sections,
imports, exports and resource offsets are preserved. Requires pefile.
"""
from pathlib import Path
import base64,csv,hashlib,io,re,sys,zipfile
import pefile

PREFIX=re.compile(rb'(?:[A-Za-z]:/|/[a-z]/)Users/[^/\x00\r\n ]+/Documents/[^/\x00\r\n ]+/[0-9-]+/[^/\x00\r\n ]+/outputs/')

def sanitize_dll(data):
    before=pefile.PE(data=data)
    def replace(match):
        n=len(match.group())
        return b'C:/build/'+b'_'*(n-10)+b'/'
    result=PREFIX.sub(replace,data)
    after=pefile.PE(data=result)
    assert len(result)==len(data)
    for a,b in zip(before.sections,after.sections):
        if a.Characteristics & 0x20000000:
            assert a.get_data()==b.get_data(), 'Executable section changed'
    for index in [0,1,5,9,12]:
        a=before.OPTIONAL_HEADER.DATA_DIRECTORY[index]
        b=after.OPTIONAL_HEADER.DATA_DIRECTORY[index]
        assert (a.VirtualAddress,a.Size)==(b.VirtualAddress,b.Size)
        if a.Size:assert before.get_data(a.VirtualAddress,a.Size)==after.get_data(b.VirtualAddress,b.Size)
    return result

def sanitize(path):
    with zipfile.ZipFile(path) as z:files={n:z.read(n) for n in z.namelist()}
    changed=[]
    for name,data in list(files.items()):
        if name.endswith('.dll'):files[name]=sanitize_dll(data)
        elif name.endswith('/DELVEWHEEL'):
            files[name]=re.sub(rb'^Arguments:.*$',b'Arguments: [local invocation omitted; see BUILD.md for the repair command]',data,flags=re.MULTILINE)
        if files[name]!=data:changed.append(name)
    record=next(n for n in files if n.endswith('.dist-info/RECORD'))
    rows=[]
    for name,data in files.items():
        digest=base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode()
        rows.append([name,'sha256='+digest,str(len(data))] if name!=record else [name,'',''])
    stream=io.StringIO(newline='');csv.writer(stream,lineterminator='\n').writerows(rows)
    files[record]=stream.getvalue().encode()
    staging=path.with_suffix('.sanitized.whl')
    with zipfile.ZipFile(staging,'x',zipfile.ZIP_DEFLATED) as z:
        for name,data in files.items():z.writestr(name,data)
    staging.replace(path)
    return changed

if __name__=='__main__':
    for argument in sys.argv[1:]:
        path=Path(argument);print(path.name,sanitize(path))
