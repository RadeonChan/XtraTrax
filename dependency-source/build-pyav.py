"""Build unmodified PyAV sources with the local LLVM-MinGW UCRT compiler."""
from pathlib import Path
import os, runpy, sys
import setuptools
from setuptools.command.build_ext import build_ext
from setuptools._distutils.compilers.C.unix import Compiler

root = Path(__file__).resolve().parent
toolchain = Path(os.environ['XTRATRAX_TOOLCHAIN'])
os.environ['PATH'] = str(toolchain)+os.pathsep+os.environ['PATH']
import sysconfig
from distutils import sysconfig as distutils_sysconfig
compiler_config = dict(CC='x86_64-w64-mingw32-clang',
    CXX='x86_64-w64-mingw32-clang++', CFLAGS='-O2 -DMS_WIN64',
    CCSHARED='', LDSHARED='x86_64-w64-mingw32-clang -shared',
    LDCXXSHARED='x86_64-w64-mingw32-clang++ -shared',
    SHLIB_SUFFIX='.dll', AR='llvm-ar', ARFLAGS='rc')
sysconfig.get_config_vars().update(compiler_config)
distutils_sysconfig.get_config_vars().update(compiler_config)

def configure(self):
    cc = 'x86_64-w64-mingw32-clang'
    cxx = cc+'++'
    self.set_executables(compiler=cc+' -O2 -DMS_WIN64',
        compiler_so=cc+' -O2 -DMS_WIN64', compiler_cxx=cxx+' -O2',
        compiler_so_cxx=cxx+' -O2', linker_so=cc+' -shared',
        linker_so_cxx=cxx+' -shared', linker_exe=cc,
        linker_exe_cxx=cxx, archiver='llvm-ar rc')
    self.shared_lib_extension = '.dll'
Compiler.configure_system = configure

class Build(build_ext):
    def finalize_options(self):
        super().finalize_options()
        self.compiler = 'unix'
        self.parallel = 6
    def get_libraries(self, ext):
        return list(ext.libraries)+['python3' if ext.py_limited_api else 'python313']

original_setup = setuptools.setup
def setup(**kwargs):
    kwargs['cmdclass'] = dict(build_ext=Build)
    return original_setup(**kwargs)
setuptools.setup = setup
os.chdir(root/'pyav')
sys.argv = ['setup.py','--ffmpeg-dir='+str(root/'prefix'),'bdist_wheel']
runpy.run_path('setup.py', run_name='__main__')
