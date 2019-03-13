#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"All *basic* python related details"
from pathlib            import Path
from typing             import Sequence, List
from waflib.Configure   import conf
from waflib.Context     import Context
from .._utils           import YES, runall, addmissing, copyfiles, copyroot
from .._requirements    import REQ as requirements

# pylint: disable=unused-import
from ._pybind11         import PyBind11, buildpyext
from ._numpy            import Numpy
from ._nodejs           import _         # pylint: disable=reimported
from ._base             import toload
from ._linting          import Linting
from ._conda            import CondaSetup

IS_MAKE = YES
TESTS   = "__tests__", "tests"

@requirements.addcheck
def check_python_nodejs(cnf, _, version):
    "checks python's nodejs"
    requirements.programversion(cnf, 'node', version)

@runall
def configure(cnf:Context):
    "get python headers and modules"
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

def buildpymod(bld:Context, name:str, pysrc:Sequence, doremove = True, **kwargs):
    "builds a python module"
    if len(pysrc) == 0:
        return

    if getattr(bld.options, 'APP_PATH', None) is None:
        if doremove:
            removeunknowns(bld, name)
        bld(name = str(bld.path)+":py", features = "py", source = pysrc)

    srclist:  List[tuple] = []
    testlist: List[tuple] = []

    testroot            = copyroot(bld, TESTS[1])
    srcroot             = copyroot(bld, name)
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

    copyfiles(bld, name,     srclist)
    copyfiles(bld, TESTS[1], testlist)

    if getattr(bld.options, 'APP_PATH', None) is None:
        Linting.run(bld, name, [i for i,_ in srclist])

@conf
def build_python(bld:Context, name:str, version:str, **kwargs):
    "builds a python module"
    if 'python' not in requirements:
        return

    csrc    = kwargs.get('python_cpp', bld.path.ant_glob('**/*.cpp'))
    pysrc   = bld.path.ant_glob('**/*.py')
    buildpyext(bld, name, version, pysrc, csrc, **kwargs)
    buildpymod(bld, name, pysrc, **kwargs)
    copyfiles(bld,  name, bld.path.ant_glob('**/*.ipynb'))

@runall
def options(opt:Context):
    "Adding conda options"
    CondaSetup.options(opt)
    Linting.options(opt)

addmissing(locals())
