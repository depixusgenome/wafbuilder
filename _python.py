#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"All *basic* python related details"
import subprocess
import urllib.request as request
import tempfile
import re
import sys

from typing             import Sequence, List
from contextlib         import closing
from waflib.Configure   import conf
from waflib.Context     import Context # type: ignore
from waflib.Tools       import python as pytools # for correcting a bug
from pkg_resources import get_distribution
from ._utils        import (YES, Make, addconfigure, runall, copyargs,
                            addmissing, copyfiles, copytargets)
from ._cpp          import Flags as CppFlags
from ._requirements import REQ as requirements

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

def setup_conda(envname):
    u"Installs conda"
    try:
        subprocess.check_output(['conda', '--version'])
    except: # pylint: disable=bare-except
        islin = sys.platform == 'linux'
        site  = "https://repo.continuum.io/miniconda/Miniconda3-latest-"
        site += 'Linux-x86_64.sh' if islin else "Windows-x86_64.exe"
        down  = tempfile.mktemp(suffix = b'sh' if islin else b'exe')
        request.urlretrieve(site, down)
        if islin:
            subprocess.check_call(['bash', down, '-b'])
        else:
            subprocess.check_call([down, '-b'])

    subprocess.check_call(['conda', 'create', '-n', envname, 'numpy'])

@addconfigure
def numpy(cnf:Context):
    u"tests numpy and obtains its headers"
    # modules are checked by parsing REQUIRE
    if ('python', 'numpy') not in requirements:
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
        if cls._NAME not in requirements or cls._DONE:
            return
        cls._DONE = True

        check_python(cnf, 'python', requirements.version('python', 'python'))
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

def toload(_:Context):
    u"returns python features to be loaded"
    return 'python' if 'python' in requirements else ''

@requirements.addcheck
def check_python(cnf, _, version):
    u"checks the python version when necessary"
    if 'PYTHON_VERSION' in cnf.env:
        return
    cnf.check_python_version(tuple(int(val) for val in str(version).split('.')))
    cnf.check_python_headers()

@requirements.addcheck
def check_python_default(cnf, name, version):
    u"Adds a default requirement checker"
    cond = 'ver >= num('+str(version).replace('.',',')+')'
    cnf.check_python_module(name.replace("python-", ""), condition = cond)

requirements.addcheck(requirements.programversion, lang = 'python', name = 'pylint')

@requirements.addcheck
def check_python_astroid(cnf, name, version):
    u"checks pylint's astroid version"
    requirements.programversion(cnf, 'pylint', version, reg = name)

@requirements.addcheck
def check_python_mypy(cnf, name, version):
    u"checks python's mypy"
    requirements.programversion(cnf, name, version)
    cmd = [getattr(cnf.env, name.upper())[0], "--fast-parser", "-c", '"print(1)"']
    cnf.cmd_and_log(cmd)

@runall
def configure(_:Context):
    u"get python headers and modules"
    pass

def pymoduledependencies(pysrc, name = None):
    u"detects dependencies"
    patterns = tuple(re.compile(r'^\s*'+pat) for pat in
                     (r'from\s+([\w.]+)\s+import\s+', r'import\s*(\w+)'))
    mods     = set()
    path     = lambda x: open(getattr(x, 'abspath', lambda: x)(), 'r')
    for item in pysrc:
        with closing(path(item)) as stream:
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
    if any(i.get_name() == name+':pyext' for i in bld.get_all_task_gen()):
        pyext.add(name)

    deps = list(pymoduledependencies(items, name) & pyext)
    def _scan(_):
        nodes = [bld.get_tgen_by_name(dep+':pyext').tasks[-1].outputs[0] for dep in deps]
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

    if sys.version.startswith("3.5"):
        mypy   = '${MYPY} ${SRC} --silent-imports --fast-parser'
    else:
        mypy   = ('${MYPY} ${SRC}  --ignore-missing-imports '
                  +'--follow-imports=skip --fast-parser')

    pylint = ('${PYLINT} ${SRC} '
              + '--init-hook="sys.path.append(\'./\')" '
              + '--msg-template="{path}:{line}:{column}:{C}: [{symbol}] {msg}" '
              + '--disable=locally-disabled '
              + '--reports=no')
    if get_distribution("astroid").version == '1.4.8':
        pylint += ' --disable=wrong-import-order,invalid-sequence-index'
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

    if ('python', 'pylint') not in requirements:
        rules.pop()

    if ('python', 'mypy') not in requirements:
        rules.pop(1)

    def _build(item, kwargs):
        bld(source = [item],
            name   = str(item)+':'+kwargs['cls_keyword'](None).lower(),
            **kwargs)

    if name in deps:
        for _, item in copytargets(bld, name, items):
            for kwargs in rules:
                _build(item, kwargs)
    else:
        for item in items:
            for kwargs in rules:
                _build(item, kwargs)

def buildpymod(bld:Context, name:str, pysrc:Sequence):
    u"builds a python module"
    if len(pysrc) == 0:
        return
    bld      (name = str(bld.path)+":py", features = "py", source = pysrc)
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


    bldnode = bld.bldnode.make_node(bld.path.relpath())
    haspy   = len(pysrc)
    mod     = '_core'                         if haspy else name
    parent  = bld.bldnode.make_node('/'+name) if haspy else bld.bldnode
    node    = bld(features = 'subst',
                  source   = bld.srcnode.find_resource(__package__+'/_module.template'),
                  target   = name+"module.cpp",
                  name     = str(bld.path)+":pybind11",
                  nsname   = name,
                  module   = mod,
                  version  = version)
    csrc.append(node.target)

    args = copyargs(kwargs)
    args.setdefault('source',   csrc)
    args.setdefault('target',   parent.path_from(bldnode)+"/"+mod)
    args.setdefault('features', []).append('pyext')
    args.setdefault('name',     name+":pyext")

    bld.shlib(**args)

@conf
def build_python(bld:Context, name:str, version:str, **kwargs):
    u"builds a python module"
    if 'python' not in requirements:
        return

    csrc   = kwargs.get('python_cpp', bld.path.ant_glob('**/*.cpp'))
    pysrc  = bld.path.ant_glob('**/*.py')

    buildpyext(bld, name, version, pysrc, csrc, **kwargs)
    buildpymod(bld, name, pysrc)
    copyfiles(bld,name,bld.path.ant_glob('**/*.ipynb'))

def condaenv(name, reqs = None, stream = None):
    u"creates a conda yaml file"
    if reqs is None:
        reqs = tuple(requirements.runtime('python').items())

    pots = {i for i, _ in reqs}
    print('name: '+name, file = stream)
    print('channels: !!python/tuple\n-defaults\ndependencies:', file = stream)
    items = subprocess.check_output((b'conda', b'list')).split(b'\n')
    for item in items:
        item = item.decode('utf-8').split()
        if not len(item):
            continue

        if item[0] not in pots:
            continue

        if len(item) == 4:
            print(' - '+item[-1]+'::'+'='.join(item[:-1]), file = stream)
        else:
            print(' - '+'='.join(item), file = stream)

def runtest(bld, *names):
    u"runs tests"
    pyext = set(bld.env.pyextmodules)
    def _scan(_):
        deps  = list(pymoduledependencies(names, None) & pyext)
        nodes = [bld.get_tgen_by_name(dep+':pyext').tasks[-1].outputs[0] for dep in deps]
        return (nodes, [])

    bld(source      = names,
        name        = 'pytests',
        always      = True,
        color       = 'YELLOW',
        rule        = '${PYTHON} -m pytest ${SRC} ',
        scan        = _scan,
        cls_keyword = lambda _: 'Pytest')

addmissing()
