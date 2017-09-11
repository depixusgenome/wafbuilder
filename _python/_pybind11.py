#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"All *basic* python related details"
import re
from typing                 import Sequence, List
from contextlib             import closing

from waflib.Context         import Context
from .._utils               import Make, copyargs, copyroot
from .._cpp                 import Flags as CppFlags
from .._requirements        import REQ as requirements
from ._base                 import hascompiler, check_python, store

_open = lambda x: open(x, 'r', encoding = 'utf-8')

class PyBind11(Make):
    "tests pybind11 and obtains its headers"
    _NAME = 'python', 'pybind11'
    @classmethod
    def options(cls, opt):
        if cls._NAME not in requirements:
            return

        opt.get_option_group('Python Options')\
           .add_option('--pybind11',
                       dest    = 'pybind11',
                       default = None,
                       action  = 'store',
                       help    = 'pybind11 include path')

    _DONE = False
    @classmethod
    def configure(cls, cnf):
        if cls._NAME not in requirements or cls._DONE or not hascompiler(cnf):
            return
        cls._DONE = True

        check_python(cnf, 'python', requirements.version('python', 'python'))
        if getattr(cnf.options, 'pybind11', None) is not None:
            store(cnf, '-I'+cnf.options.pybind11)

        cnf.env.append_unique('CXXFLAGS_PYEXT', CppFlags.convertFlags(cnf, '-std=c++14'))
        def _build(bld):
            lib_node = bld.srcnode.make_node('pybind11example.cpp')
            lib_node.write("""
                          #include <pybind11/pybind11.h>

                          int add(int i, int j) { return i + j; }
                          using namespace pybind11;

                          PYBIND11_PLUGIN(example)
                          {
                                module m("example", "pybind11 example");
                                m.def("add", &add, "A function which adds two numbers");
                                return m.ptr();
                          }
                          """, 'w')
            bld.shlib(features='pyext cxxshlib',
                      source=[lib_node],
                      target='pybind11example')

        cnf.check_cxx(build_fun = _build,
                      msg       = 'checking for pybind11',
                      mandatory = True)

def pymoduledependencies(pysrc, name = None):
    "detects dependencies"
    patterns = tuple(re.compile(r'^\s*'+pat) for pat in
                     (r'from\s+([\w.]+)\s+import\s+', r'import\s*(\w+)'))
    mods = set()
    path = lambda x: _open(getattr(x, 'abspath', lambda: x)())
    for item in pysrc:
        with closing(path(item)) as stream:
            for line in stream: # pylint: disable=not-an-iterable
                if 'import' not in line:
                    continue

                for pat in patterns:
                    ans = pat.match(line)
                    if ans is None:
                        continue

                    grp = ans.group(1)
                    if grp.startswith('._core') and name is not None:
                        mods.add(name)
                    else:
                        mods.add(grp)
    return mods

def findpyext(bld:Context, items:Sequence):
    "returns a list of pyextension in that module"
    if not hascompiler(bld):
        return

    names = list(items)
    bld.env.pyextmodules = set()
    for name in names:
        path = bld.path.make_node(str(name))
        if haspyext(path.ant_glob('**/*.cpp')):
            bld.env.pyextmodules.add(name[name.rfind('/')+1:])

def haspyext(csrc):
    "detects whether pybind11 is used"
    pattern = re.compile(r'\s*#\s*include\s*["<]pybind11')
    for item in csrc:
        with closing(_open(item.abspath())) as stream:
            # pylint: disable=not-an-iterable
            if any(pattern.match(line) is not None for line in stream):
                return True
    return False

def buildpyext(bld     : Context,
               name    : str,
               version : str,
               pysrc   : Sequence,
               csrc    : List,
               **kwargs):
    "builds a python extension"
    if len(csrc) == 0:
        return

    if name not in bld.env.pyextmodules and not haspyext(csrc):
        return

    mod    = '_core' if len(pysrc) else name
    parent = copyroot(bld, name if len(pysrc) else None)
    target = parent.path_from(bld.bldnode.make_node(bld.path.relpath()))+"/"+mod

    node   = bld(features = 'subst',
                 source   = bld.srcnode.find_resource(__package__.replace('.', '/')
                                                      +'/_module.template'),
                 target   = name+"module.cpp",
                 name     = str(bld.path)+":pybind11",
                 nsname   = name,
                 module   = mod,
                 version  = version)
    csrc.append(node.target)

    args = copyargs(kwargs)
    args.setdefault('source',   csrc)

    args.setdefault('target',   target)
    args.setdefault('features', []).append('pyext')
    args.setdefault('name',     name+":pyext")

    bld.shlib(**args)
