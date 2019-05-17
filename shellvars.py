#l!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Allows defining the conda environment to use.

This is used by 'call_waf.py' in order to set-up the env prior to launching
the waf script in a child process. In this way the environment variables are
set from the start of the *true* script.

The environment settings, required for the CI, are also printed-out using the
*info* method.

Finally, "condaenvname" allows extracting the conda env defined at configuration
and re-use it *build* and *test* modes.
"""
import os
import sys
import subprocess

from typing         import Tuple
try:
    from .git       import branch
except ImportError:
    from git import branch

def condaenvname(cnf, **kwa):
    "get the env name"
    if isinstance(cnf, (list, tuple)):
        envname = 'unspecified'
        if '-e' in cnf:
            envname = cnf[cnf.index('-e')+1]
        elif '--envname' in cnf:
            envname = cnf[cnf.index('--envname')+1]
        else:
            envname = next(
                (k.split('=')[1] for k in cnf if k.startswith('--envname=')),
                'unspecified'
            )
    else:
        envname = kwa.get('envname', 'root')
        if envname == 'root':
            envname = getattr(getattr(cnf, 'options', cnf), 'condaenv', 'root')
        if envname == 'root':
            envname = getattr(getattr(cnf, 'env', cnf), 'CONDA_DEFAULT_ENV', 'base')
        print(envname)

    if envname.lower() == 'branch':
        envname = branch()
    return envname

def shellvars(cnf, master = None, **kwa)-> Tuple[Tuple[str, str]]:
    "return a script for setting the path"
    envname = condaenvname(cnf, **kwa)
    if envname == 'unspecified':
        envname = 'base'

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

    if envname not in avail and master in avail:
        # use the master env
        envname = master

    if envname not in avail or envname in ('base', 'root'):
        # use the base env
        return ()

    return (
        ('CONDA_DEFAULT_ENV', envname),
        ('CONDA_PREFIX',      avail[envname]),
        ('PYTHON_HOST_PROG',  avail[envname]+'/bin/python'),
        ('PYTHON3_HOST_PROG', avail[envname]+'/bin/python3'),
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

def shell(cnf, output = 'stdout', shells =  ('build', 'configure', 'test'), **kwa):
    """
    updates python shell vars to update

    Arguments:
        * cnf: can be a list such as sys.argv or a Context
        * output: governs the behaviour of the method:
            * 'stdout': prints a shell script to stdout
            * None:
                * if 'shellvars' is in the 'cnf' argument: prints a shell
                script to stdout and terminates the program.
                * if 'info' is in the 'cnf' argument: sets the shell vars,
                prints all conda info to stdout and terminates the program.
                * if any of 'shells' is in the 'cnf' argument:
                sets the shell vars and returns.
        * shells: see 'output'
    """
    if output is None:
        if 'condaenvname' in cnf:
            return ''
        if 'shellvars' in cnf:
            shell(cnf, 'stdout', **kwa)
            exit(0)
        elif 'info' in cnf:
            shell(cnf, 'shell', **kwa)
            info()
            exit(0)

        elif any(i in cnf for i in shells):
            try:
                envname = condaenvname(cnf, **kwa)
                if envname == 'unspecified':
                    envname = (
                        subprocess
                        .check_output([sys.executable, *cnf[:cnf.index("waf")+1], "condaenvname"])
                        .decode('utf-8')
                        .split('\n')[1]
                        .strip()
                    )
                    cnf = list(cnf)+["-e", envname]
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