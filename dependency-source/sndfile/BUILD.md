# Pinned libsndfile and SoundFile build

The six source archives in this directory are exact upstream Git trees.
`provenance.json` records tags, commit IDs, archive hashes, build-tool versions,
and the resulting DLL hash/imports. `libsndfile 1.2.2` is linked statically with
libogg 1.3.5, libFLAC 1.4.3, libvorbis 1.3.7, and libopus 1.5.2. Its MPEG
backend is disabled. XtraTrax handles MP3 input through its separate pinned
FFmpeg build. The SoundFile Python implementation remains upstream 0.14.0;
the wheel recipe replaces the DLL payload and dependency notices.

## Reproduction

1. Extract the archives as sibling directories named `libsndfile`, `ogg`,
   `flac`, `vorbis`, `opus`, and `python-soundfile` beside these scripts.
2. Create a Python environment with the pinned CMake, Ninja, setuptools and
   wheel versions recorded in `provenance.json`. The build used CPython 3.13.5
   on Windows x64 and LLVM-MinGW 20260616 UCRT x86_64, targeting x86_64.
3. Set `XTRATRAX_TOOLCHAIN` to the LLVM-MinGW `bin` directory before running `build-libraries.py`.
4. Run `python build-libraries.py`, then `python build-wheel.py` from this
   environment. The first builds all native inputs in dependency order; the
   second creates `python-soundfile/dist/soundfile-0.14.0-py2.py3-none-win_amd64.whl`.
5. Install the local wheel. Do not substitute the public PyPI wheel with the
   same version number: its bundled native library is different.

The build limits dependency search to its local prefix. It does not use vcpkg
or obtain unpinned codec binaries. Path-sanitized CMake caches are included as build
evidence; they contain neutral example paths and are not intended to be copied into a
fresh build. Scripts generate fresh caches. Hash reproducibility across
different toolchains or paths is not asserted.

libsndfile is dynamically loaded and uses LGPL 2.1-or-later; the linked Xiph
libraries use their included BSD-style notices. Full source archives retain
their original license files, including those for components not built here.
Only libFLAC is linked from FLAC, not its GPL command-line utilities or C++
library. Retain applicable notices and corresponding source when distributing.

Run the parent directory sanitize_wheel.py on the resulting wheel to remove
local build prefixes from diagnostic strings before validating a release.
