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
    from git        import branch

def _envnames(cnf):
    return (
        subprocess
        .run(cnf, check = True, stdout = subprocess.PIPE, stderr = subprocess.PIPE).stdout
        .decode('utf-8')
        .strip()
        .split('\n')
    )

ENV_DEFAULT = "master"
ENV_BASE    = "base"
ENV_BRANCH  = "base"
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
    return envname

def shellvars(cnf, default = ENV_BRANCH, **kwa)-> Tuple[Tuple[str, str]]:
    "return a script for setting the path"
    envname = condaenvname(cnf, default = default, **kwa)
    if sys.platform.startswith("win"):
        raise NotImplementedError("Needs coding the conda env discovery & setup")

    conda = kwa.get('conda', getattr(cnf, 'env', {}).get('CONDA', 'conda'))
    avail = {
        i.strip()[:i.find(' ')]: i.strip()[i.rfind(' ')+1:]
        for i in _envnames([conda, 'info', '-e'])
    }

    if envname not in avail:
        envname = (
            default     if default     in avail else
            ENV_DEFAULT if ENV_DEFAULT in avail else
            ENV_BASE
        )

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
                    for i in _envnames([sys.executable, *cnf[:cnf.index("waf")+1], "condaenvname"]):
                        if i.startswith("CONDA_ENV_NAME:"):
                            envname = i.split(":")[1].strip()
                            break
                    else:
                        envname = "base"

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
