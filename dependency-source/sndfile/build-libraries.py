"""Pinned-source libsndfile build; all codec inputs live beside this script."""
from pathlib import Path
import os, subprocess, sys
root=Path(__file__).resolve().parent
tools=Path(os.environ['XTRATRAX_TOOLCHAIN'])
scripts=Path(sys.executable).parent
env=os.environ.copy();env['PATH']=os.pathsep.join(map(str,[tools,scripts,Path(env.get('SystemRoot',r'C:\Windows'))/'System32']))
prefix=root/'prefix'
common=['-G','Ninja','-DCMAKE_BUILD_TYPE=Release','-DCMAKE_SYSTEM_NAME=Windows',
    '-DCMAKE_C_COMPILER='+str(tools/'x86_64-w64-mingw32-clang.exe'),
    '-DCMAKE_CXX_COMPILER='+str(tools/'x86_64-w64-mingw32-clang++.exe'),
    '-DCMAKE_MAKE_PROGRAM='+str(scripts/'ninja.exe'),
    '-DCMAKE_INSTALL_PREFIX='+str(prefix),'-DCMAKE_PREFIX_PATH='+str(prefix),
    '-DCMAKE_FIND_ROOT_PATH='+str(prefix),'-DCMAKE_FIND_ROOT_PATH_MODE_LIBRARY=ONLY',
    '-DCMAKE_FIND_ROOT_PATH_MODE_INCLUDE=ONLY','-DCMAKE_FIND_ROOT_PATH_MODE_PACKAGE=ONLY',
    '-DCMAKE_POLICY_VERSION_MINIMUM=3.5','-DBUILD_TESTING=OFF','-DBUILD_SHARED_LIBS=OFF']
projects=[('ogg',[]),('flac',['-DBUILD_CXXLIBS=OFF','-DBUILD_PROGRAMS=OFF','-DBUILD_EXAMPLES=OFF','-DBUILD_DOCS=OFF','-DINSTALL_MANPAGES=OFF']),
    ('vorbis',[]),('opus',['-DOPUS_BUILD_PROGRAMS=OFF','-DOPUS_BUILD_TESTING=OFF','-DOPUS_BUILD_SHARED_LIBRARY=OFF']),
    ('libsndfile',['-DBUILD_SHARED_LIBS=ON','-DBUILD_PROGRAMS=OFF','-DBUILD_EXAMPLES=OFF',
      '-DENABLE_MPEG=OFF','-DENABLE_EXTERNAL_LIBS=ON','-DENABLE_EXPERIMENTAL=OFF',
      '-DENABLE_CPACK=OFF','-DCMAKE_C_FLAGS=-DFLAC__NO_DLL'])]
for name,options in projects:
    build=root/('build-'+name)
    with (root/(name+'-build.log')).open('w') as log:
        for args in [ ['-S',str(root/name),'-B',str(build),*common,*options],
            ['--build',str(build),'--parallel','8'],['--install',str(build)]]:
            subprocess.run([str(scripts/'cmake.exe'),*args],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    print('Built',name,flush=True)
