# LAME encoder

Pinned upstream source: LAME 3.100, downloaded from the source_url recorded in
provenance.json. The unmodified source archive and GNU Library GPL v2 license
are included. config.h selects a portable encoder-only Windows x64 build.

Build with Python 3.13 and LLVM-MinGW 20260616 UCRT:

```
python build.py C:/toolchain/bin/x86_64-w64-mingw32-clang.exe
```

The DLL uses Windows UCRT and KERNEL32; it has no mpg123 or FFmpeg dependency.
No separate encoder installation is required by the application. The dynamic
library is replaceable; rebuilt versions require updating its runtime hash
after validation. Compiler warnings from the unmodified upstream source are
retained. Do not treat successful compilation as audio validation.

The application encodes prepared stereo audio at 44.1 kHz, 320 kbps CBR,
quality 2. Suitable existing MP3 streams are repacked without re-encoding.
