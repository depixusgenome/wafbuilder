#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"All *basic* python related details"
from waflib.Context    import Context
from waflib.Tools      import python as pytools # for correcting a bug

from .._requirements   import REQ as requirements

pytools.PYTHON_MODULE_TEMPLATE = '''
import os, pkg_resources
NAME = '%s'
vers = None
try:
    vers = pkg_resources.get_distribution(NAME).version
except:
    try:
        current_module = __import__(NAME)
        vers = getattr(current_module, '__version__', None)

        if vers is None:
            vers = getattr(current_module, 'version', None)

        if vers is None:
            vers = __import__(NAME+'.version').version

        if vers is not None:
            vers = getattr(vers, '__version__', vers)
    except:
        import subprocess
        cmd = ["conda", "list", NAME]
        try:
            try:
                ret = subprocess.check_output(cmd)
            except FileNotFoundError:
                ret = subprocess.check_output(cmd, shell = True)
            out = ret.strip().split(b"\\n")
            if len(out) == 4:
                vers = next((i for i in out[-1].split(b" ")[1:] if i != b""), None)
                if vers is not None:
                    vers = vers.decode('utf-8')
        except:
            pass
print('unknown version' if vers is None else str(vers))
'''

def hascompiler(cnf:Context):
    "whether the waf file mentions c++"
    return cnf.env.CC_NAME or cnf.env.CXX_NAME

def store(cnf:Context, flg:str):
    "store more python flags"
    if hascompiler(cnf):
        for item in 'PYEXT', 'PYEMBED':
            cnf.parse_flags(flg, uselib_store=item)

def toload(_:Context):
    "returns python features to be loaded"
    return 'python' if 'python' in requirements else ''

@requirements.addcheck
def check_python(cnf, _, version):
    "checks the python version when necessary"
    if 'PYTHON_VERSION' in cnf.env:
        return
    cnf.check_python_version(tuple(int(val) for val in str(version).split('.')))
    if hascompiler(cnf):
        cnf.check_python_headers()

@requirements.addcheck
def check_python_default(cnf, name, version):
    "Adds a default requirement checker"
    cond = 'ver >= num('+str(version).replace('.',',')+')'
    cnf.check_python_module(name.replace("python-", ""), condition = cond)
