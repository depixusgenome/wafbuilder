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

class JuliaLint:
    """
    Sets up a server for linting julia files
    """
    def __init__(self, fname = str(Path(__file__).parent/"_julialint.jl")):
        self.cnt    = itertools.count()
        self.file   = fname
        self.server = None

    def lint(self, bld, src = None):
        "runs the lint on the file"
        if src is None:
            src  = bld.path.ant_glob('**/*.jl')

        if len(src) == 0:
            return

        if self.server is None:
            self.server = subprocess.Popen(["julia", self.file],
                                           stdout = subprocess.DEVNULL,
                                           stderr = subprocess.DEVNULL)
        for inp in src:
            grp = f'julia_{next(self.cnt)}'
            bld.add_group(grp, move = False)
            bld(source = [inp],
                color  = 'BLUE',
                rule   = f'julia {self.file} ${{SRC}}',
                group  = grp,
                cls_keyword = lambda _: 'Julia')

JLINT = JuliaLint()

@conf
def build_julia(bld:Context, name:str, _:str, **_2):
    "builds a python module"
    if 'julia' not in requirements:
        return

    copyfiles(bld, name, bld.path.ant_glob("**/*.jl"))
    #JLINT.lint(bld)
