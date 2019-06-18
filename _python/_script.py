#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"All *basic* python related details"
from pathlib            import Path
from typing             import Sequence, List, Tuple
from waflib.Configure   import conf
from waflib.Context     import Context
from ..git              import (
    version as _version,  lasthash, lastdate, isdirty, lasttimestamp
)
from .._utils           import YES, runall, addmissing, copyfiles, copyroot
from .._requirements    import REQ as requirements

# pylint: disable=unused-import
from ._pybind11         import PyBind11, buildpyext
from ._numpy            import Numpy
from ._base             import toload
from ._linting          import Linting
from ._conda            import CondaSetup

IS_MAKE = YES
TESTS   = "__tests__", "tests"

@runall
def configure(cnf:Context):
    "get python headers and modules"
    cnf.env.append_value('SYS_INCS', 'PYEXT')
    cnf.env.append_value('SYS_INCS', 'PYEMBED')
    CondaSetup.configure(cnf)
    load(cnf)  # type: ignore # pylint: disable=undefined-variable

def removeunknowns(bld:Context, name:str):
    "remove unknown python files"
    srcpath = Path(str(bld.path))
    bldpath = Path(str(bld.bldnode))/name
    ind     = len(str(bldpath))+1
    vals    = [val for val in bldpath.glob("**/*.py")
               if not (srcpath/str(val)[ind:]).exists()]
    if len(vals):
        def _rem(*_):
            for path in vals:
                path.unlink()
                cache = path.parent/"__pycache__"
                for j in cache.glob(path.stem+".*"):
                    Path(cache/j).unlink()

        bld(always      = True,
            name        = f"{name}: rm {' '.join(i.name for i in vals)}",
            cls_keyword = lambda _: 'unknowns',
            rule        = _rem)

def _pymod_splitfiles(bld, name, pysrc) -> Tuple[List[tuple], List[tuple]]:
    srclist:  List[tuple] = []
    testlist: List[tuple] = []

    testroot = copyroot(bld, TESTS[1])
    srcroot  = copyroot(bld, name)
    for itm in pysrc:
        path   = Path(str(itm))
        parent = path.parent
        while parent.name not in (TESTS[0], name):
            parent = parent.parent

        tgt  = str(path.relative_to(parent))
        if parent.name == name:
            srclist.append((itm, srcroot.make_node(tgt)))
        else:
            testlist.append((itm, testroot.make_node(tgt)))
    return srclist, testlist

def _pymod_build(bld, name, pysrc, doremove):
    srclist, testlist = _pymod_splitfiles(bld, name, pysrc)
    copyfiles(bld, name,     srclist)
    copyfiles(bld, TESTS[1], testlist)

    if doremove:
        removeunknowns(bld, name)

    bld(
        name         = str(bld.path)+":py",
        features     = "py",
        source       = pysrc,
        install_path = None
    )

    Linting.run(bld, name, [i for i,_ in srclist])

def _pymod_install(bld, name, pysrc):
    env     = bld.env
    ouext   = ".pyc" if env.PYC else ".pyo" if env.PYO else ".py"
    inext   = (
        '.py'              if ouext == '.py' else
        (
            (f'.{env.PYTAG}' if env.PYTAG and not env.NOPYCACHE else '')
            + ouext
        )
    )
    cache   = "__pycache__" if env.PYTAG in inext else ''

    rundir  = Path(bld.run_dir)
    blddir  = Path(bld.out_dir)
    instdir = Path(bld.installcodepath(direct = True))
    for node, _  in _pymod_splitfiles(bld, name, pysrc)[0]:
        src = Path(str(node))
        inp = blddir/((src.parent/cache/src.stem).with_suffix(inext).relative_to(bld.run_dir))
        out = src.with_suffix(ouext)
        out = out.relative_to(rundir/out.relative_to(rundir).parts[0])
        bld.install_as(str(instdir/out), bld.root.find_node(str(inp)))

def buildpymod(bld:Context, name:str, pysrc:Sequence, doremove = True, **_):
    "builds a python module"
    if len(pysrc) == 0:
        return

    if bld.cmd == "build":
        _pymod_build(bld, name, pysrc, doremove)
    else:
        _pymod_install(bld, name, pysrc)

@conf
def build_python(bld:Context, name:str, version:str, **kwargs):
    "builds a python module"
    if 'python' not in requirements:
        return

    csrc    = kwargs.get('python_cpp', bld.path.ant_glob('**/*.cpp'))
    pysrc   = [i for i in bld.path.ant_glob('**/*.py') if Path(str(i)).stem[0] !='.']
    buildpyext(bld, name, version, pysrc, csrc, **kwargs)
    buildpymod(bld, name, pysrc, **kwargs)
    if bld.cmd == 'build':
        copyfiles(bld,  name, bld.path.ant_glob('**/*.ipynb'))

@conf
def build_python_version_file(bld:Context):
    "creates a version.py file"
    bld(
        features          = 'subst',
        source            = bld.srcnode.find_resource(
            __package__.replace(".", "/")+'/_version.template'
        ),
        target            = "version.py",
        name              = str(bld.path)+":version",
        version           = _version(),
        lasthash          = lasthash(),
        lastdate          = lastdate(),
        isdirty           = isdirty(),
        timestamp         = lasttimestamp(),
        cpp_compiler_name = bld.cpp_compiler_name(),
        ** bld.installcodepath()
    )

@runall
def options(opt:Context):
    "Adding conda options"
    CondaSetup.options(opt)
    Linting.options(opt)

addmissing(locals())
