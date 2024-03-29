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
from   pathlib import Path
import os
import sys
import subprocess

from typing         import Tuple
try:
    from .git       import branch, origin
except ImportError:
    from git        import branch, origin

def _envnames(cnf):
    for i in (False, True):
        try:
            return (
                subprocess
                .run(
                    cnf,
                    check  = True,
                    stdout = subprocess.PIPE,
                    stderr = subprocess.PIPE,
                    shell  = i
                ).stdout
                .decode('utf-8')
                .strip()
                .split('\n')
            )
        except FileNotFoundError:
            pass
    raise RuntimeError("Could not find conda environment names")

ENV_BASE    = "base"
ENV_BRANCH  = "branch"
ENV_ORIGIN  = "origin"
ENV_DEFAULT = [ENV_BRANCH, ENV_ORIGIN, "master", "base"]
def condaenvname(cnf, default = ENV_BRANCH, **kwa):
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
        get     = lambda x, y: getattr(getattr(cnf, x, cnf), y, None)
        envname = kwa.get('envname', None)
        if not envname:
            envname = get('options', 'condaenv')
        if not envname:
            envname = get('env', 'CONDA_DEFAULT_ENV')
        if not envname:
            envname = default

    if envname.lower() == ENV_BRANCH:
        envname = branch()
        if envname == 'master':
            envname = origin().lower()
    elif envname.lower() == ENV_ORIGIN:
        envname = origin().lower()
    return envname

def shellvars(cnf, defaults = None, **kwa)-> Tuple[Tuple[str, str]]:
    "return a script for setting the path"
    if not defaults:
        defaults = ENV_DEFAULT

    envname = condaenvname(cnf, default = defaults[0], **kwa)
    conda   = kwa.get('conda', None)
    if not conda and hasattr(cnf, 'env'):
        conda = cnf.env.CONDA
        if conda and isinstance(conda, (list, tuple)):
            conda = conda[0]
    if not conda:
        conda = "conda"

    avail = {
        i.strip()[:i.find(' ')]: i.strip()[i.rfind(' ')+1:]
        for i in _envnames([conda, 'info', '-e'])
        if i[0] != '#' and ' ' in i.strip()
    }

    brch = branch()
    orig = origin().lower()
    if envname not in avail:
        for i in defaults:
            envname = (
                brch if i == ENV_BRANCH else
                orig if i == ENV_ORIGIN else
                i
            )
            if i == ENV_BRANCH and orig in avail and brch == 'master':
                envname = orig
            if envname in avail:
                break
        else:
            envname = ENV_BASE
    root = Path(avail[envname])
    if sys.platform.startswith("win"):
        binary = root
        path   = (
            f'{binary};'
            +''.join(f'{root/"Library"/i/"bin"};' for i in ('mingw-w64', 'usr', ''))
            +''.join(f'{root/i};' for i in ('Scripts', 'bin'))
            +';'.join(
                i for i in os.environ["PATH"].split(';')
                if 'condabin' in i or 'miniconda3' not in i
            )
        )
    else:
        binary = root/"bin"
        path   = f'{binary}:{os.environ["PATH"]}'
    return (
        ('CONDA_DEFAULT_ENV', envname),
        ('CONDA_PREFIX',      str(root)),
        ('PYTHON_HOST_PROG',  str(binary/'python')),
        ('PYTHON3_HOST_PROG', str(binary/'python3')),
        ('PATH',              str(path))
    )

def info():
    "print info"
    print("ENV **********************")
    print(f"CONDA_DEFAULT_ENV: {os.environ.get('CONDA_DEFAULT_ENV', '')}")
    print(f"PATH: {os.environ.get('PATH', '')}")
    print("OTHER **********************")
    print(f"ORIGIN: {origin()}")
    print(f"BRANCH: {branch()}")
    for txt, cmd in (
            ("\nCOMPILERS *****************",           ['clang', '--version']),
            ("",                                        ['g++-8', '--version']),
            ("\nCONDA INFO *********************",      ['conda', 'info', '-a']),
            ("\nCONDA PACKAGES *********************",  ['conda', 'list', '--explicit']),
    ):
        out = subprocess.run(cmd, capture_output = True)
        print(txt)
        if out.stdout:
            print(out.stdout.decode('utf-8'))
        if out.stderr:
            print(out.stderr.deconde('utf-8'), file = sys.stderr)
        out.check_returncode()

def shell(cnf, output = 'stdout', shells =  ('build', 'configure', 'test', 'html'), **kwa):
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
