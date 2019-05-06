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
def check_nodejs(cnf, name, version):
    "check for nodejs"
    mand = not sys.platform.startswith("win")
    requirements.programversion(cnf, 'node', version, mandatory = mand)

@requirements.addcheck
def check_nodejs_typescript(cnf, _, version):
    "check for coffeelint"
    mand = not sys.platform.startswith("win")
    requirements.programversion(cnf, "tsc", version, mandatory = mand)

def build_typescript(bld:Context, name:str):
    "builds all coffee files"
    copyfiles(bld, name, bld.path.ant_glob('**/*.ts'))

@requirements.addcheck
def check_nodejs_coffeelint(cnf, name, version):
    "check for coffeelint"
    mand = not sys.platform.startswith("win")
    requirements.programversion(cnf, name, version, mandatory = mand)

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

def build_coffeescript(bld:Context, name:str):
    "builds all coffee files"
    coffees = bld.path.ant_glob('**/*.coffee')
    copyfiles(bld, name, coffees)
    if (
            ('nodejs', 'coffeescript') in requirements
            and getattr(bld.options, 'APP_PATH', None) is None
    ):
        if 'COFFEE' in bld.env:
            bld(source = coffees)

        if bld.options.DO_PY_LINTING:
            coffeelint(bld)

@conf
def build_nodejs(bld:Context, name:str, _1, **_2):
    "builds all coffee/typescript files"
    build_typescript(bld, name)
    build_coffeescript(bld, name)
