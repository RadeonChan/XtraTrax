# Patch notes

## 0.3.11

- Reduced playlist size by storing added songs as compressed audio.
- Compatible MP3s import without another lossy encode.
- Fixed subtle audio artifacts in compressed playback.
- Fixed oversized-playlist errors; playlists exceeding the game's 2 GiB soundtrack limit stop before installation.
- Added Select All, Ctrl+A, and a scrollbar to the song list.
- Added blue glass-style progress bars for the current track and total preparation.
- Check volume-matched audio peaks after encoding.

## 0.3.10

- Replaced the bundled demonstration WAV with a smaller 320 kbps MP3.

## 0.3.9

- Renamed the backup folder to XtraTraxBackup.

## 0.3.8

- Updated documentation and release packaging.

## 0.3.7

- Added the Breathe compact-disc application icon.
- Clarified the ASI loader requirement and playlist replacement instructions.

## 0.3.6

- Centered the replacement confirmation over the application.
- Added Windows application and taskbar icons.

## 0.3.5

- Fixed incomplete backups blocking later installation or restoration.
- Added recovery-receipt verification before rollback.
- Fixed a MagiPack log-path buffer boundary error.

## 0.3.0-0.3.4

- Expanded capacity to 100 added songs (127 total).
- Added local error reports and stronger file verification.
- Bundled a smaller audio-only runtime with pinned dependency sources.
- Isolated build dependencies and verified packaged runtime files.

## Earlier versions

- Added support for US 1.2, LGU and MagiPack v5 installations.
- Added custom song information, optional wider song banners and volume matching.
- Added backup, playlist replacement and original-music restoration.
