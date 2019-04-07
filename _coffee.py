#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"All *basic* coffeescript related details"
import sys

from pathlib            import Path
from waflib             import TaskGen
from waflib.Configure   import conf
from waflib.Context     import Context

from ._utils        import copyfiles
from ._requirements import REQ as requirements

TaskGen.declare_chain(
    name         = 'coffees',
    rule         = '${COFFEE} --compile -o ${TGT} ${SRC}',
    ext_in       = '.coffee',
    ext_out      = '.js',
    shell        = False,
    reentrant    = False,
    install_path = None)

@requirements.addcheck
def check_coffee(cnf, name, version):
    "check for coffeescript"
    mand = not sys.platform.startswith("win")
    requirements.programversion(cnf, name, version, mandatory = mand)

@requirements.addcheck
def check_coffee_coffeelint(cnf, name, version):
    "check for coffeelint"
    mand = not sys.platform.startswith("win")
    requirements.programversion(cnf, name, version, mandatory = mand)

@conf
def build_coffee(bld:Context, name:str, _1, **_2):
    u"builds all coffee files"
    if 'coffee' not in requirements:
        return
    if 'COFFEE' not in bld.env or getattr(bld.options, 'APP_PATH', None) is not None:
        return

    tsx = bld.path.ant_glob('**/*.tsx')
    copyfiles(bld, name, tsx)

    coffees = bld.path.ant_glob('**/*.coffee')
    if len(coffees) == 0:
        return

    bld(source = coffees)
    copyfiles(bld, name, coffees)

    if bld.options.DO_PY_LINTING and 'COFFEELINT' in bld.env:
        if 'coffeelint' not in bld.group_names:
            bld.add_group('coffeelint', move = False)

        cmd = (
            '${COFFEELINT} --reporter=csv --file=%s ${SRC}'
            % str(next(
                (Path(direct)/'coffeelintrc').resolve()
                for direct in ('', 'linting', '..', '../linting')
                if (Path(direct)/'coffeelintrc').exists()
            ))
        )
        for i in coffees:
            bld(
                source = [i],
                rule        = cmd,
                color       = 'BLUE',
                cls_keyword = lambda _: 'CoffeeLint',
                group  = 'coffeelint',
            )
