# Building the packaged source

The source ZIP and repository include assets, plugin templates, UI text and
the demonstration track. Extract the entire source ZIP before building.

The release audit used Windows x64, Python 3.13.5, and an isolated virtual
environment. From this Source directory, run `python -m pip install -r requirements.txt`; this installs the supplied audio dependency wheels from `vendor`, not the public PyPI wheel. The rebuild script verifies their hashes and the installed DLLs before building.
From `Source`, run `python rebuild.py` to copy the supplied assets and build
`dist-0.3.11/XtraTrax/XtraTrax.exe`. This uses the shipped plugin templates.
It does not require a game installation or launch a game.

The supplied `assets/XtraTrax.ico` is used for the executable and window icons.
It contains nine sizes from 16 through 256 pixels. To reproduce this asset,
install Pillow 12.3.0 in a separate tools environment and run `build_icon.py`.
It scales the retained Breathe PNG rendering; the original SVG, PNG, license
and attribution are in `third-party-icon`.
Pillow is not required by the application or ordinary frontend rebuild.

## Rebuilding the native plugins

After the frontend rebuild has populated `Source/assets`, use the packaged
scripts below. Substitute the full path to an i686 LLVM-MinGW compiler.
`llvm-nm.exe` must be in that compiler's directory. `pefile` is a build dependency.

```powershell
python build_plugin.py 'C:\toolchain\bin\i686-w64-mingw32-clang.exe'
python build_lgu_plugin.py 'C:\toolchain\bin\i686-w64-mingw32-clang.exe'
python build_lgu_plugin.py 'C:\toolchain\bin\i686-w64-mingw32-clang.exe' --us-loose
python rebuild.py
```

The scripts build the archive, LGU loose-file, and US loose-file profiles,
respectively, and rediscover their exported configuration offsets. Keep each
template together with its generated JSON descriptor; never reuse stale offsets.
The audited toolchain was LLVM-MinGW 20260616 UCRT x86_64, targeting i686.

Rebuilt native templates require matching regenerated descriptors and regression
validation before distribution. Toolchain or path changes may alter hashes.
Gameplay equivalence is not established by successful compilation alone.

Third-party components retain their licenses. See dependency-source for audio
dependency sources and build recipes.
