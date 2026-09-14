# Technical reference

## Compatibility

Supported profiles are the verified US 1.2 executable with original SDATA
archive, LGU with its verified loose music files, and MagiPack v5 with its
verified US executable and loose music files. Executable and audio hashes are
checked independently. Unknown files and mixed archive/loose layouts are refused.
Compatibility with every other mod or repack is not established.

A working 32-bit dinput8 ASI loader must load SCRIPTS/NativeTrax.asi.
The installer checks for dinput8.dll; presence alone does not establish loader
identity or functionality. No loader or original game files are distributed.

## Music

Supports 1-100 additions, up to 30 minutes per track and a 2 GiB output limit.
Inputs: WAV, FLAC, MP3, M4A (AAC/ALAC), Ogg (Vorbis/Opus). Mono and stereo are
supported; surround and multiple audio streams are refused. Damaged or protected
files may be refused. Output is 44.1 kHz, 16-bit stereo. Mono is duplicated at
unchanged amplitude. Matching WAV/FLAC input bypasses conversion. Compressed
files may retain codec padding. Resampling and quantization can change samples;
out-of-range input can clip. No separate Python or converter install is needed.

Volume matching is off by default. When enabled, it uses limiting and up to four
gain adjustments toward -9 LUFS, with verified peaks at or below -1 dBTP. The
limiter uses 192 kHz oversampling, 5 ms lookahead/attack, 50 ms release, latency
compensation and no automatic makeup gain. This is a product setting, not a
recovered engine constant. It can change dynamics and cause pumping; the target
is not guaranteed for every recording. Silence and very short clips receive no
loudness boost. Original input files remain untouched.

Metadata fields are limited to 255 UTF-8 bytes. Unsupported characters may not
display correctly. Wide banners do not guarantee arbitrary text will fit.
Added-track preferences use decoded audio identity; changing volume processing
can reset them. Changing metadata does not intentionally reset preferences.

## Installation and recovery

Apply prepares the new soundtrack before replacing installed files. Initial
backups are staged and verified before becoming active. Replacements save
verified recovery copies and a receipt. Write failures attempt rollback; the
next Apply or Restore resumes interrupted recovery. Unknown outside changes
cause refusal. Replacement is recoverable per file, not a filesystem-wide atomic
transaction. Preserve backups and recovery files after an error.

Restore returns the music originally backed up for that supported distribution,
removes the soundtrack plugin and retains the backup. It does not convert a
repack's soundtrack into the retail soundtrack.

Backup folders: XtraTraxBackup,
XtraTraxBackup.restored (possibly numbered). The installed plugin is
SCRIPTS/NativeTrax.asi. Do not rename backup files manually.

## Diagnostics

Apply/Restore failures save reports under %LOCALAPPDATA%/XtraTrax/Diagnostics.
Reports contain local paths, hashes and error details, not file contents. They
are not uploaded automatically. Review a report before sharing it. Failure to
save a report does not replace the original error or prevent rollback.

Plugin logs are NativeTrax.log, NativeTrax-LGU.log or NativeTrax-MagiPack.log in
the Windows temporary directory. Preferences use the corresponding
NFSU2-NativeTrax INI file under LocalAppData.

## Dependencies and source

The audio runtime uses pinned FFmpeg n8.1, PyAV 18.1.0 and libsndfile 1.2.2 with
libogg 1.3.5, FLAC 1.4.3, Vorbis 1.3.7 and Opus 1.5.2. FFmpeg networking and
unused codecs/programs are disabled; MP3 decoding uses FFmpeg rather than the
disabled libsndfile MPEG backend. Sources, build recipes, configuration records
and notices are included under dependency-source, vendor and third-party folders.
Build records use neutral paths. Release wheels have local diagnostic/configuration
path prefixes sanitized without changing executable sections; see
dependency-source/sanitize_wheel.py and SANITIZATION.json.

See PLUGIN-BUILD.md for building and CHANGELOG.md for version changes. No project-wide source
license is supplied. Third-party licenses remain applicable.

The bundled demonstration song is Dead at Dawn by RadeonChan, from Dance of
the Afterlife EP, distributed with the rights holder's permission. Icon artwork
is Breathe media-optical; attribution and its license are in third-party-icon.
