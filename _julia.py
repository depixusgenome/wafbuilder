#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"All *basic* python related details"
from waflib.Configure import conf
from waflib.Context   import Context
from ._requirements   import REQ as requirements
from ._utils          import copyfiles

@requirements.addcheck
def check_julia(cnf, name, version):
    "checks pylint's astroid version"
    requirements.programversion(cnf, 'julia', version, reg = name)

@conf
def build_julia(bld:Context, name:str, _:str, **_2):
    "builds a python module"
    if 'julia' not in requirements:
        return

    src  = bld.path.ant_glob('**/*.jl')
    copyfiles(bld, name, src)
