#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"All *basic* coffeescript related details"
from subprocess         import check_output
import sys
from pathlib            import Path
from waflib             import Logs, Errors, TaskGen
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

@requirements.addcheck
def check_coffee_typescript(cnf, name, version):
    "check for coffeelint"
    mand = not sys.platform.startswith("win")
    requirements.programversion(cnf, "tsc", version, mandatory = mand)

def coffeelintcompiler(bld, tgt, *_):
    "use coffee lint"
    path = str(next(
        (Path(direct)/'coffeelintrc').resolve()
        for direct in ('', 'linting', '..', '../linting')
        if (Path(direct)/'coffeelintrc').exists()
    ))

    out = check_output(
        [bld.env['COFFEELINT'][0], f'--file={path}', '--reporter=csv', str(tgt)]
    ).strip().split(b'\n')[1:]

    if out:
        msg = 'Coffeelint: '+b'\n'.join(out).decode('utf-8')
        Logs.error(msg)
        raise Errors.WafError(msg)

def coffeelint(bld):
    "add rules for linting coffee files"

    if 'COFFEELINT' not in bld.env:
        return

    if 'coffeelint' not in bld.group_names:
        bld.add_group('coffeelint', move = False)

    for i in bld.path.ant_glob('**/*.coffee'):
        bld(
            source      = [i],
            rule        = lambda x, *_: coffeelintcompiler(bld, x, *_),
            color       = 'BLUE',
            cls_keyword = lambda _: 'CoffeeLint',
            group       = 'coffeelint',
        )

@conf
def build_coffee(bld:Context, name:str, _1, **_2):
    "builds all coffee files"
    if 'coffee' in requirements:
        tsx     = bld.path.ant_glob('**/*.ts')
        coffees = bld.path.ant_glob('**/*.coffee')
        copyfiles(bld, name, tsx+coffees)

        if getattr(bld.options, 'APP_PATH', None) is None:
            if 'COFFEE' in bld.env:
                bld(source = coffees)

            if bld.options.DO_PY_LINTING:
                coffeelint(bld)
