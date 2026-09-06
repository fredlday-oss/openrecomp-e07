
import sys
import os
import distutils.sysconfig
from setuptools._distutils.ccompiler import new_compiler
compiler = new_compiler()
distutils.sysconfig.customize_compiler(compiler)
compiler.add_include_dir('.')
try:
    objs = compiler.compile(['generated.c', 'D:/OpenRecomp/openrecomp-e07/scratch/harness.c'])
    compiler.link_executable(objs, 'host_execution')
except Exception as e:
    print(e)
    sys.exit(1)
