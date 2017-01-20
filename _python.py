#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"All *basic* python related details"
import subprocess
import re

from typing             import Sequence, List
from contextlib         import closing
from waflib.Configure   import conf
from waflib.Context     import Context # type: ignore
from waflib.Tools       import python as pytools # for correcting a bug

from ._utils        import (YES, Make, addconfigure, runall,
                            addmissing, copyfiles, copytargets)
from ._cpp          import Flags as CppFlags
from ._requirements import (requirementcheck, isrequired, checkprogramversion,
                            requiredversion)

pytools.PYTHON_MODULE_TEMPLATE = '''
import os, pkg_resources
NAME = '%s'
vers = None
try:
    vers = pkg_resources.get_distribution(NAME).version
except:
    try:
        current_module = __import__(NAME)
        vers = getattr(current_module, '__version__', None)

        if vers is None:
            vers = getattr(current_module, 'version', None)

        if vers is None:
            vers = __import__(NAME+'.version').version

        if vers is not None:
            vers = getattr(vers, '__version__', vers)
    except:
        pass
print('unknown version' if vers is None else str(vers))
'''

IS_MAKE = YES

def _store(cnf:Context, flg:str):
    for item in 'PYEXT', 'PYEMBED':
        cnf.parse_flags(flg, uselib_store=item)

@addconfigure
def numpy(cnf:Context):
    u"tests numpy and obtains its headers"
    # modules are checked by parsing REQUIRE
    if not isrequired('python', 'numpy'):
        return

    cmd = cnf.env.PYTHON[0]                                     \
        + ' -c "from numpy.distutils import misc_util as n;'    \
        + ' print(\'-I\'.join([\'\']+n.get_numpy_include_dirs()))"'
    flg = subprocess.check_output(cmd, shell=True).decode("utf-8")
    _store(cnf, flg)

class PyBind11(Make):
    u"tests pybind11 and obtains its headers"
    _NAME = 'python', 'pybind11'
    @classmethod
    def options(cls, opt):
        if not isrequired(*cls._NAME):
            return

        opt.get_option_group('Python Options')\
           .add_option('--pybind11',
                       dest    = 'pybind11',
                       default = None,
                       action  = 'store',
                       help    = 'pybind11 include path')

    @classmethod
    def configure(cls, cnf):
        if not isrequired(*cls._NAME):
            return

        if cnf.options.pybind11 is not None:
            _store(cnf, '-I'+cnf.options.pybind11)

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

def loads():
    u"returns python features to be loaded"
    if not isrequired('python'):
        return ""
    return 'python'


requirementcheck(lambda *_: None, lang = 'python', name = 'python')

@requirementcheck
def check_python_default(cnf, name, version):
    u"Adds a default requirement checker"
    cond = 'ver >= num('+version.replace('.',',')+')'
    cnf.check_python_module(name.replace("python-", ""), condition = cond)

requirementcheck(checkprogramversion, lang = 'python', name = 'pylint')
requirementcheck(checkprogramversion, lang = 'python', name = 'mypy')

@runall
def configure(cnf:Context):
    u"get python headers and modules"
    version = requiredversion('python', 'python')
    cnf.check_python_version(tuple(int(val) for val in version.split('.')))
    cnf.check_python_headers()

def pymoduledependencies(pysrc, name = None):
    u"detects dependencies"
    patterns = tuple(re.compile(r'^\s*'+pat) for pat in
                     (r'from\s+([\w.]+)\s+import\s+', r'import\s*(\w+)'))
    mods     = set()
    for item in pysrc:
        with closing(open(item.abspath(), 'r')) as stream:
            for line in stream:
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
    u"returns a list of pyextension in that module"
    names = list(items)
    bld.env.pyextmodules = set()
    for name in names:
        path = bld.path.make_node(str(name))
        if haspyext(path.ant_glob('**/*.cpp')):
            bld.env.pyextmodules.add(name[name.rfind('/')+1:])

def haspyext(csrc):
    u"detects whether pybind11 is used"
    pattern = re.compile(r'\s*#\s*include\s*["<]pybind11')
    for item in csrc:
        with closing(open(item.abspath(), 'r')) as stream:
            if any(pattern.match(line) is not None for line in stream):
                return True
    return False

def checkpy(bld:Context, name:str, items:Sequence):
    u"builds tasks for checking code"
    if len(items) == 0:
        return

    pyext = set(bld.env.pyextmodules)
    pyext.add(name)

    deps = list(pymoduledependencies(items, name) & pyext)
    def _scan(_):
        nodes = [bld.get_tgen_by_name(dep+'pyext').tasks[-1].outputs[0] for dep in deps]
        return (nodes, [])

    def _checkencoding(tsk):
        headers = '#!/usr/bin/env python3\n', '# -*- coding: utf-8 -*-\n'

        with open(tsk.inputs[0].abspath(), 'r') as stream:
            errs    = [True]*2
            try:
                for i, head in enumerate(headers):
                    errs[i] = next(stream) != head
            except IOError as ex:
                bld.fatal("Could not open file", ex)
            except StopIteration:
                pass

        tpl = 'Missing or incorrect header line %d: '
        msg = '\t- '.join((tpl % i + headers[i])  for i in range(len(errs)) if errs[i])
        if len(msg):
            bld.fatal('In file %s:\n\t- ' % tsk.inputs[0].abspath()+msg)

    mypy   = '${MYPY} ${SRC} --silent-imports --fast-parser'
    pylint = ('${PYLINT} ${SRC} '
              + '--init-hook="sys.path.append(\'./\')" '
              + '--msg-template="{path}:{line}:{column}:{C}: [{symbol}] {msg}" '
              + '--disable=locally-disabled '
              + '--reports=no')
    rules  = [dict(color       = 'CYAN',
                   rule        = _checkencoding,
                   cls_keyword = lambda _: 'python headers'),
              dict(color       = 'BLUE',
                   rule        = mypy,
                   scan        = _scan,
                   cls_keyword = lambda _: 'MyPy'),
              dict(color       = 'YELLOW',
                   rule        = pylint,
                   scan        = _scan,
                   cls_keyword = lambda _: 'PyLint'),
             ] # type: List

    if name in deps:
        for _, item in copytargets(bld, name, items):
            for kwargs in rules:
                bld(source = [item], **kwargs)
    else:
        for item in items:
            for kwargs in rules:
                bld(source = [item], **kwargs)

def buildpymod(bld:Context, name:str, pysrc:Sequence):
    u"builds a python module"
    if len(pysrc) == 0:
        return
    bld      (features = "py", source = pysrc)
    checkpy  (bld, name, pysrc)
    copyfiles(bld, name, pysrc)

def buildpyext(bld     : Context,
               name    : str,
               version : str,
               pysrc   : Sequence,
               csrc    : List,
               **kwargs):
    u"builds a python extension"
    if len(csrc) == 0:
        return

    if name not in bld.env.pyextmodules and not haspyext(csrc):
        return

    args    = kwargs
    bldnode = bld.bldnode.make_node(bld.path.relpath())
    haspy   = len(pysrc)
    mod     = '_core'                         if haspy else name
    parent  = bld.bldnode.make_node('/'+name) if haspy else bld.bldnode
    node    = bld(features = 'subst',
                  source   = bld.srcnode.find_resource(__package__+'/_module.template'),
                  target   = name+"module.cpp",
                  nsname   = name,
                  module   = mod,
                  version  = version)
    csrc.append(node.target)

    args.setdefault('source',   csrc)
    args.setdefault('target',   parent.path_from(bldnode)+"/"+mod)
    args.setdefault('features', []).append('pyext')
    args.setdefault('name',     name+"pyext")

    bld.shlib(**args)

@conf
def build_py(bld:Context, name:str, version:str, **kwargs):
    u"builds a python module"
    if not isrequired('python'):
        return

    csrc   = bld.path.ant_glob('**/*.cpp')
    pysrc  = bld.path.ant_glob('**/*.py')

    buildpymod(bld, name, pysrc)
    buildpyext(bld, name, version, pysrc, csrc, **kwargs)
    copyfiles(bld,name,bld.path.ant_glob('**/*.ipynb'))

def condaenv(stream, name, reqs = None):
    u"creates a conda yaml file"
    if reqs is None:
        reqs = tuple(i for i, (_, j) in  requiredversion('python').items() if j)

    print('name: '+name, file = stream)
    print('channels: !!python/tuple\n-defaults\ndependencies:', file = stream)
    items = subprocess.check_output((b'conda', b'list')).split(b'\n')
    for item in items:
        item = item.decode('utf-8').split()
        if not (len(item) and any(name == item[0] for name in reqs)):
            continue

        if len(item) == 4:
            print(' - '+item[-1]+'::'+'='.join(item[:-1]), file = stream)
        else:
            print(' - '+'='.join(item), file = stream)

addmissing(locals())
