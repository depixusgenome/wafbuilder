#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"All *basic* python related details"
from pathlib            import Path
from typing             import Sequence
from waflib.Configure   import conf
from waflib.Context     import Context
from .._utils           import YES, runall, addmissing, copyfiles
from .._requirements    import REQ as requirements

# pylint: disable=unused-import
from ._pybind11         import PyBind11, buildpyext
from ._numpy            import Numpy
from ._nodejs           import _         # pylint: disable=reimported
from ._base             import toload
from ._linting          import Linting
from ._conda            import CondaSetup

IS_MAKE = YES

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

def buildpymod(bld:Context, name:str, pysrc:Sequence):
    "builds a python module"
    if len(pysrc) == 0:
        return

    if getattr(bld.options, 'APP_PATH', None) is None:
        removeunknowns(bld, name)
        bld(name = str(bld.path)+":py", features = "py", source = pysrc)
        Linting.run(bld, name, pysrc)
    copyfiles(bld, name, pysrc)

@conf
def build_python(bld:Context, name:str, version:str, **kwargs):
    "builds a python module"
    if 'python' not in requirements:
        return

    csrc    = kwargs.get('python_cpp', bld.path.ant_glob('**/*.cpp'))
    pysrc   = bld.path.ant_glob('**/*.py')
    buildpyext(bld, name, version, pysrc, csrc, **kwargs)
    buildpymod(bld, name, pysrc)
    copyfiles(bld,  name, bld.path.ant_glob('**/*.ipynb'))

@runall
def options(opt:Context):
    "Adding conda options"
    CondaSetup.options(opt)

addmissing(locals())
