# Rebuilding the audio dependency

The supplied wheel was built on Windows x64 using CPython 3.13.5, Git for
Windows bash, and LLVM-MinGW 20260616 UCRT x86_64 targeting x86_64.

1. Extract the two source archives here to sibling `ffmpeg` and `pyav` folders.
2. Create an isolated Python environment. Install the pinned tools in
   `build-environment.txt` except its `av` entry: that is the resulting local
   wheel, not an input. Its neutral URL is an example location.
3. Set XTRATRAX_TOOLCHAIN to your LLVM-MinGW bin directory (use a
   Git Bash path when running the shell script). Run the shell script through Git for Windows bash. It uses
   the toolchain's `mingw32-make` and installs DLLs and headers in `prefix`.
4. Run `python build-pyav.py`. Its process-local setuptools adapter uses the
   UCRT compiler with CPython's import library. Upstream PyAV source is unchanged.
5. Run from this directory:

```powershell
python -m delvewheel repair pyav/dist/av-18.1.0-cp311-abi3-win_amd64.whl --add-path prefix/bin -w wheels
```

The repaired wheel includes seven FFmpeg DLLs. No external codec libraries are
enabled. Source commit IDs, configuration, original DLL hashes and import tables
are in `dependency-inventory.json`; the release wheel hash is in
`../vendor/audio-runtime.json`.

Rebuild hashes may differ with toolchain changes or build metadata. Validate
such a build before replacing the release runtime manifest. The manifest
intentionally prevents an unreviewed wheel from silently entering a release.
Exact source archives and full license texts are included here. Retain
applicable notices and corresponding source when distributing these libraries.

Build paths in configuration records have been replaced with neutral examples.
After wheel repair, run `python sanitize_wheel.py wheels/av-18.1.0-cp311-abi3-win_amd64.whl`.
This removes embedded local build prefixes without changing executable code.
