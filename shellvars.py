#l!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Conda shell vars"
import os
import sys
import subprocess

from typing         import Tuple
try:
    from .git       import branch
except ImportError:
    from git import branch

def getenvname(cnf, **kwa):
    "get the env name"
    envname = 'base'
    if isinstance(cnf, (list, tuple)):
        if '-e' in cnf:
            envname = cnf[cnf.index('-e')+1]
        elif '--envname' in cnf:
            envname = cnf[cnf.index('--envname')+1]
        else:
            envname = next(
                (k.split('=')[1] for k in cnf if k.startswith('--envname=')),
                'base'
            )
    else:
        envname = kwa.get('envname', getattr(getattr(cnf, 'options', cnf), 'condaenv', 'base'))

    if envname.lower() == 'branch':
        envname = branch()
    return envname

def shellvars(cnf, **kwa)-> Tuple[Tuple[str, str]]:
    "return a script for setting the path"
    envname = getenvname(cnf, **kwa)
    if envname in ('root', 'base'):
        return ()

    path  = os.environ.get('PATH', '')
    cname = os.environ.get('CONDA_DEFAULT_ENV', 'base')
    if envname in path or envname == cname:
        return ()

    if sys.platform.startswith("win"):
        raise NotImplementedError("Needs coding the conda env discovery & setup")

    conda = kwa.get('conda', getattr(cnf, 'env', {}).get('CONDA', 'conda'))
    avail = {
        i.strip()[:i.find(' ')]: i.strip()[i.rfind(' ')+1:]
        for i in (
            subprocess
            .check_output([conda, 'info', '-e'])
            .decode('utf-8')
            .split('\n')
        )
    }

    if envname not in avail:
        raise KeyError(f"Missing conda env '{envname}'")

    return (
        ('CONDA_DEFAULT_ENV', envname),
        ('CONDA_PREFIX',      avail[envname]),
        ('PYTHON_HOST_PROG',  avail[envname]+'/bin/python'),
        ('PYTHON3_HOST_PROG',  avail[envname]+'/bin/python3'),
        ('PATH',              f'{avail[envname]}/bin:{os.environ["PATH"]}')
    )

def info():
    "print info"
    print("\nCOMPILERS *****************")
    subprocess.check_call(['clang', '--version'])
    print("")
    subprocess.check_call(['g++-8', '--version'])
    print("\nCONDA INFO *********************")
    subprocess.check_call(['conda', 'info', '-a'], shell = False)

    print("\nCONDA PACKAGES *********************")
    subprocess.check_call(['conda', 'list', '--explicit'], shell = False)

def shell(cnf, output = 'stdout', **kwa):
    "return pythone shell vars to update"
    if output is None:
        if 'shellvars' in cnf:
            shell(cnf, 'stdout', **kwa)
            exit(0)
        elif 'info' in cnf:
            shell(cnf, 'shell', **kwa)
            info()
            exit(0)

        elif 'build' in cnf or 'configure' in cnf:
            try:
                return shell(cnf, 'shell', **kwa)
            except KeyError:
                return ""

    itms = shellvars(cnf, **kwa)
    if output == 'shell':
        os.environ.update(**dict(itms))
        return os.environ.get('CONDA_DEFAULT_ENV', 'base')
    keyw, sep = (
        ('set -x', ' ') if 'fish' in os.environ.get('SHELL', '') else
        ('export', '=') # bash
    )
    script = '\n'.join(f'{keyw} {i}{sep}{j}' for i, j in itms)
    if output == 'stdout':
        print(script)
    return script
