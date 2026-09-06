import subprocess
from pathlib import Path
import sys

def build():
    build_exe = f"""
import sys
import setuptools
from setuptools._distutils.ccompiler import new_compiler
import distutils.sysconfig
compiler = new_compiler()
distutils.sysconfig.customize_compiler(compiler)
compiler.add_include_dir('.')
try:
    objs = compiler.compile(['artifacts/mips32_translation_v1/generated.c', 'scratch/harness.c'])
    compiler.link_executable(objs, 'artifacts/mips32_translation_v1/host_execution')
except Exception as e:
    print(e)
    sys.exit(1)
"""
    Path("scratch/build.py").write_text(build_exe)
    subprocess.run([sys.executable, "scratch/build.py"], check=True)

if __name__ == "__main__":
    build()
