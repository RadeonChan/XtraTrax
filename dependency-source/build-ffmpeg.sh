#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")"
export PATH="${XTRATRAX_TOOLCHAIN:?Set XTRATRAX_TOOLCHAIN to your compiler bin directory}:$PATH"
mkdir -p prefix
prefix="$(pwd)/prefix"
cd ffmpeg
./configure --prefix="$prefix" --target-os=mingw32 --arch=x86_64 \
 --cc=x86_64-w64-mingw32-clang --cxx=x86_64-w64-mingw32-clang++ \
 --ar=llvm-ar --ranlib=llvm-ranlib --nm=llvm-nm --strip=llvm-strip \
 --enable-shared --disable-static --disable-autodetect --disable-gpl \
 --disable-nonfree --disable-version3 --disable-network --disable-programs \
 --disable-doc --disable-debug --disable-x86asm --disable-everything \
 --enable-protocol=file \
 --enable-demuxer=wav,flac,mp3,mov,ogg,aac \
 --enable-parser=aac,aac_latm,flac,mpegaudio,opus,vorbis \
 --enable-decoder=aac,aac_fixed,aac_latm,alac,flac,mp3,mp3float,mp3adu,mp3adufloat,mp3on4,mp3on4float,opus,vorbis,pcm_s8,pcm_u8,pcm_s16le,pcm_s16be,pcm_s24le,pcm_s24be,pcm_s32le,pcm_s32be,pcm_f32le,pcm_f32be,pcm_f64le,pcm_f64be \
 --enable-filter=abuffer,abuffersink,aresample,aformat,volume,alimiter,loudnorm,anull
mingw32-make -j8
mingw32-make install
