#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"All *basic* coffeescript related details"
from waflib             import TaskGen
from waflib.Configure   import conf
from waflib.Context     import Context

from wafbuilder._utils  import copyfiles, requirements, checkversion

@conf
def find_coffee(cnf):
    u"get python headers and modules"
    checkversion(cnf, 'coffee', requirements('coffee').pop('coffee'))

TaskGen.declare_chain(
    name         = 'coffees',
    rule         = '${COFFEE} --compile -o ${TGT} ${SRC}',
    ext_in       = '.coffee',
    ext_out      = '.js',
    shell        = False,
    reentrant    = False,
    install_path = None)

@conf
def configure_coffee(cnf:Context):
    u"configures coffee"
    import wafbuilder
    cnf.load("coffee", wafbuilder.__path__, 'find_coffee') 

@conf
def build_coffee(bld:Context, name:str, _1, **_2):
    u"builds all coffee files"
    coffees = bld.path.ant_glob('**/*.coffee')
    if len(coffees):
        bld      (source = coffees)
        copyfiles(bld, name, coffees)
