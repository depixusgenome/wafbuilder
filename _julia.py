#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"All *basic* python related details"
import itertools
import subprocess
from pathlib import Path
from waflib.Configure import conf
from waflib.Context   import Context
from ._requirements   import REQ as requirements
from ._utils          import copyfiles

@requirements.addcheck
def check_julia(cnf, name, version):
    "checks pylint's astroid version"
    requirements.programversion(cnf, 'julia', version, reg = name)

JULIA_CNT   = itertools.count()
JULIA_FILE  = str(Path(__file__).parent/"_julialint.jl")
LINT_SERVER = subprocess.Popen(["julia", JULIA_FILE],
                               stdout = subprocess.DEVNULL,
                               stderr = subprocess.DEVNULL)
@conf
def build_julia(bld:Context, name:str, _:str, **_2):
    "builds a python module"
    if 'julia' not in requirements:
        return

    src  = bld.path.ant_glob('**/*.jl')
    copyfiles(bld, name, src)

    for inp in src:
        grp = f'julia_{next(JULIA_CNT)}'
        bld.add_group(grp, move = False)
        bld(source = [inp],
            color  = 'BLUE',
            rule   = f'julia {JULIA_FILE} ${{SRC}}',
            group  = grp,
            cls_keyword = lambda _: 'Julia')
