#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"All *basic* python related details"
import subprocess
import urllib.request as request
import tempfile
import re
import os
import sys
import json
from   pathlib              import Path

from   distutils.version    import LooseVersion

from typing                 import Sequence, List
from contextlib             import closing
from pkg_resources          import get_distribution

from waflib                 import Logs
from waflib.Configure       import conf
from waflib.Context         import Context # type: ignore
from waflib.Tools           import python as pytools # for correcting a bug
from ._utils                import (YES, Make, addconfigure, runall, copyargs,
                                    addmissing, copyfiles, copytargets, copyroot)
from ._cpp                  import Flags as CppFlags
from ._requirements         import REQ as requirements

CHANNELS = ['', ' -c conda-forge']

_open = lambda x: open(x, 'r', encoding = 'utf-8')

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
    "tests numpy and obtains its headers"
    # modules are checked by parsing REQUIRE
    if ('python', 'numpy') not in requirements:
        return

    cmd = cnf.env.PYTHON[0]                                     \
        + ' -c "from numpy.distutils import misc_util as n;'    \
        + ' print(\'-I\'.join([\'\']+n.get_numpy_include_dirs()))"'
    flg = subprocess.check_output(cmd, shell=True).decode("utf-8")
    _store(cnf, flg)

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
    "returns python features to be loaded"
    return 'python' if 'python' in requirements else ''

@requirements.addcheck
def check_python(cnf, _, version):
    "checks the python version when necessary"
    if 'PYTHON_VERSION' in cnf.env:
        return
    cnf.check_python_version(tuple(int(val) for val in str(version).split('.')))
    cnf.check_python_headers()

@requirements.addcheck
def check_python_default(cnf, name, version):
    "Adds a default requirement checker"
    cond = 'ver >= num('+str(version).replace('.',',')+')'
    cnf.check_python_module(name.replace("python-", ""), condition = cond)

requirements.addcheck(requirements.programversion, lang = 'python', name = 'pylint')

@requirements.addcheck
def check_python_astroid(cnf, name, version):
    "checks pylint's astroid version"
    requirements.programversion(cnf, 'pylint', version, reg = name)

@requirements.addcheck
def check_python_mypy(cnf, name, version):
    "checks python's mypy"
    requirements.programversion(cnf, name, version)
    cmd = getattr(cnf.env, name.upper())+ ["--version"]
    if float(cnf.cmd_and_log(cmd).split()[1]) <= 0.501:
        cnf.env[name.upper()] += ['--fast-parser']

    cmd = getattr(cnf.env, name.upper()) + ["-c", '"print(1)"']
    cnf.cmd_and_log(cmd)

@requirements.addcheck
def check_python_nodejs(cnf, _, version):
    "checks python's nodejs"
    requirements.programversion(cnf, 'node', version)

@runall
def configure(_:Context):
    "get python headers and modules"
    pass

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

class Linting:
    "all rules for checking python"
    @staticmethod
    def __pylintrule():
        pylint = ('${PYLINT} ${SRC} '
                  + '--init-hook="sys.path.append(\'./\')" '
                  + '--msg-template="{path}:{line}:{column}:{C}: [{symbol}] {msg}" '
                  + '--disable=locally-disabled '
                  + '--reports=no')

        if get_distribution("pylint").version >= '1.7.1':  # pylint: disable=no-member
            pylint += ' --score=n'

        if (get_distribution("astroid").version == '1.4.8' # pylint: disable=no-member
                or sys.platform.startswith("win")):
            pylint += ' --disable=wrong-import-order,invalid-sequence-index'

        for name in ('', 'linting', '..', '../linting'):
            path = Path(name)/'pylintrc'
            if path.exists():
                pylint += ' --rcfile="'+str(path.resolve())+'"'
                break

        return dict(color       = 'YELLOW',
                    rule        = pylint,
                    cls_keyword = lambda _: 'PyLint')

    @staticmethod
    def __mypyrule():
        mypy   = ('${MYPY} ${SRC}  --ignore-missing-imports '
                  +'--follow-imports=skip')
        for name in ('', 'linting', '..', '../linting'):
            path = Path(name)/'mypy.ini'
            if path.exists():
                mypy += ' --config-file="'+str(path.resolve())+'"'
                break
        return dict(color       = 'BLUE',
                    rule        = mypy,
                    cls_keyword = lambda _: 'MyPy')

    @staticmethod
    def __encodingrule(bld):
        def _checkencoding(tsk):
            headers = '#!/usr/bin/env python3\n', '# -*- coding: utf-8 -*-\n'

            with _open(tsk.inputs[0].abspath()) as stream:
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

        return dict(color       = 'CYAN',
                    rule        = _checkencoding,
                    cls_keyword = lambda _: 'python headers')

    @classmethod
    def run(cls, bld:Context, name:str, items:Sequence):
        "builds tasks for checking code"
        if len(items) == 0:
            return

        pyext = set(bld.env.pyextmodules)
        if any(i.get_name() == name+':pyext' for i in bld.get_all_task_gen()):
            pyext.add(name)

        deps = list(pymoduledependencies(items, name) & pyext)
        def _scan(_):
            nodes = [bld.get_tgen_by_name(dep+':pyext').tasks[-1].outputs[0] for dep in deps]
            return (nodes, [])

        rules = [cls.__encodingrule(bld)] # type: List
        if ('python', 'pylint') in requirements:
            rules.append(cls.__pylintrule())
            rules[-1]['scan'] = _scan

        if ('python', 'mypy') in requirements:
            rules.append(cls.__mypyrule())
            rules[-1]['scan'] = _scan

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

def checkpy(bld:Context, name:str, items:Sequence):
    "builds tasks for checking code"
    return Linting.run(bld, name, items)

def buildpymod(bld:Context, name:str, pysrc:Sequence):
    "builds a python module"
    if len(pysrc) == 0:
        return

    if getattr(bld.options, 'APP_PATH', None) is None:
        bld      (name = str(bld.path)+":py", features = "py", source = pysrc)
        Linting.run(bld, name, pysrc)
    copyfiles(bld, name, pysrc)

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
                 source   = bld.srcnode.find_resource(__package__+'/_module.template'),
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

@conf
def build_python(bld:Context, name:str, version:str, **kwargs):
    "builds a python module"
    if 'python' not in requirements:
        return

    csrc   = kwargs.get('python_cpp', bld.path.ant_glob('**/*.cpp'))
    pysrc  = bld.path.ant_glob('**/*.py')

    buildpyext(bld, name, version, pysrc, csrc, **kwargs)
    buildpymod(bld, name, pysrc)
    copyfiles(bld,  name, bld.path.ant_glob('**/*.ipynb'))

@runall
def options(opt:Context):
    "Adding conda options"
    CondaSetup.options(opt)

class CondaSetup:
    "installs / updates a conda environment"
    def __init__(self, cnf = None, **kwa):
        self.envname = kwa.get('envname',     getattr(cnf, 'condaenv',   'root'))
        self.packages = kwa.get('packages', getattr(cnf, 'packages', '').split(','))
        if self.packages == ['']:
            self.packages = []

        self.minvers = kwa.get('minversion',  getattr(cnf, 'minversion',  False))
        self.rtime   = kwa.get('runtimeonly', getattr(cnf, 'runtimeonly', False))
        self.copy    = kwa.get('copy', None)

        if getattr(cnf, 'pinned', '') == '':
            lst = requirements.pinned()
            lst.extend(i.replace('python-', '') for i in lst if 'python-' in i)
        else:
            lst = [i.strip().lower() for i in getattr(cnf, 'pinned', '').split(',')]
        self.pinned  = kwa.get('pinned',  lst)

    @staticmethod
    def options(opt:Context):
        "defines options for conda setup"
        grp = opt.add_option_group('condasetup options')
        grp.add_option('-e', '--envname',
                       dest    = 'condaenv',
                       action  = 'store',
                       default = 'root',
                       help    = u"conda environment name")

        grp.add_option('--pinned',
                       dest    = 'pinned',
                       action  = 'store',
                       default = '',
                       help    = u"packages with pinned versions")

        grp.add_option('-m', '--min-version',
                       dest    = 'minversion',
                       action  = 'store_true',
                       default = False,
                       help    = u"install requirement minimum versions by default")

        grp.add_option('-r', '--runtime-only',
                       dest    = 'runtimeonly',
                       action  = 'store_true',
                       default = False,
                       help    = u"install only runtime modules")

        grp.add_option('-p', '--packages',
                       dest    = 'packages',
                       action  = 'store',
                       default = '',
                       help    = u"consider only these packages")

    @staticmethod
    def __run(cmd):
        try:
            Logs.info('conda '+cmd)
            subprocess.check_call(['conda']+cmd.split(' '),
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
        except: # pylint: disable=bare-except
            return True
        return False

    @staticmethod
    def __read(cmd):
        return subprocess.check_output(['conda']+cmd.split(' '),
                                       stderr=subprocess.DEVNULL)

    @classmethod
    def __download(cls):
        if cls.__run('--version'):
            islin = sys.platform == 'linux'
            site  = "https://repo.continuum.io/miniconda/Miniconda3-latest-"
            site += 'Linux-x86_64.sh' if islin else "Windows-x86_64.exe"
            down  = tempfile.mktemp(suffix = 'sh' if islin else 'exe')
            request.urlretrieve(site, down)
            if islin:
                subprocess.check_call(['bash', down, '-b'])
            else:
                subprocess.check_call([down, '-b'])

    def __createenv(self):
        "create conda environment"
        if self.__run('list -n '+ self.envname):
            version = requirements('python', 'numpy')
            cmd =  'create --yes -n '+self.envname  + " numpy>="+str(version)
            if self.__ismin('numpy'):
                cmd = cmd.replace('>=', '=')

            self.__run(cmd)

    def __ismin(self, name):
        return self.minvers or name.lower() in self.pinned

    def __pipversion(self, name, version):
        "gets the version with pip"
        cur = subprocess.check_output([self.__pip(), 'show', name]).split(b'\n')[1]
        cur = cur.split(b':')[1].decode('utf-8').strip()
        if LooseVersion(cur) < version:
            return False
        return True

    def __condaupdate(self, res, name, version):
        "updates a module with conda"
        if res.get(name, (0, '<pip>'))[1] == '<pip>':
            return False

        cmd = '-n '+self.envname+ ' ' + name
        if version is not None:
            cmd += ('=' if self.__ismin(name) else '>=') + str(version)

        if res[name][1] not in ('defaults', ''):
            cmd += ' -c '+res[name][1]

        if self.__run('install '+cmd+' --yes'):
            self.__run('remove -n %s %s --yes' % (self.envname, name))
            return False
        return True

    def __condainstall(self, name, version):
        "installs a module with conda"
        cmd = '-n '+self.envname+ ' "' + name
        if version is not None:
            cmd += ('=' if self.__ismin(name) else '>=') + str(version)
        cmd += '"'

        for channel in CHANNELS:
            if not self.__run('install ' + cmd + channel+ ' --yes'):
                return True
            Logs.info("failed on channel '%s'", channel)

        if version is not None:
            return self.__condainstall(name, None)
        return False

    def __currentlist(self):
        res = {}
        for line in self.__read('list -n '+self.envname).decode('utf-8').split('\n'):
            if len(line) == 0 or line[0] == '#':
                continue
            vals         = line.split()
            channel      = vals[-1]
            if len(vals) == 3 and channel != '<pip>':
                channel = ''
            res[vals[0]] = vals[1], channel
        return res

    def __pip(self):
        info = json.loads(self.__read('info --json').decode('utf-8'))
        envs = info['envs']
        def _get(env):
            if sys.platform.startswith('win'):
                path = Path(env)/"Scripts"/"pip.exe"
            else:
                path = Path(env)/"bin"/"pip"
            if not path.exists():
                self.__condainstall('pip', None)
            return str(path.resolve())

        for env in envs:
            if env.endswith(self.envname):
                return _get(env)

        return _get(info['default_prefix'])

    def __isgood(self, name, version, res):
        if name not in res:
            return False
        if self.__ismin(name):
            return LooseVersion(res[name][0]) == version
        return LooseVersion(res[name][0]) >= version

    def __python_run(self):
        "Installs python modules"
        res  = self.__currentlist()
        itms = requirements('python', runtimeonly = self.rtime)
        itms.update((i[len('python_'):], j)
                    for i, j in requirements('cpp', runtimeonly = self.rtime).items()
                    if i.startswith('python_'))
        if len(self.packages):
            itms = {i: j for i, j in itms.items() if i in self.packages}

        for name, version in itms.items():
            if name == 'python':
                continue

            Logs.info("checking: %s=%s", name, version)
            if self.__isgood(name, version, res):
                continue

            if self.__condaupdate(res, name, version):
                continue

            try:
                if (self.__pipversion(name, version)
                        and self.__ismin(name)):
                    continue
            except subprocess.CalledProcessError:
                pass

            if (res.get(name, (0, 0))[1] != '<pip>'
                    and self.__condainstall(name, version)):
                continue

            cmd = [self.__pip(), 'install']
            if version is None:
                cmd += [name]
            elif self.__ismin(name):
                cmd += ["%s==%s" % (name, version)]
            else:
                cmd += ["%s>=%s" % (name, version)]
            subprocess.check_call(cmd)

    def __coffee_run(self):
        "Installs coffee/js modules"
        itms  = requirements('coffee', runtimeonly = self.rtime)
        if len(self.packages):
            itms = {i: j for i, j in itms.items() if i in self.packages}

        if len(itms) == 0:
            return

        def _get(env):
            if sys.platform.startswith('win'):
                path = Path(env)/"Scripts"/"npm"
                if not path.exists():
                    path = Path(env)/"npm"
            else:
                path = Path(env)/"bin"/"npm"

            assert path.exists(), path

            return str(path)

        npm  = None
        info = json.loads(self.__read('info --json').decode('utf-8'))
        for env in info['envs']:
            if env.endswith(self.envname):
                npm = _get(env)
                if npm is not None:
                    break
        else:
            if self.envname == 'root':
                npm = _get(info['default_prefix'])
        assert npm is not None

        for info in itms.items():
            if info[0] == 'coffee':
                info = 'coffeescript', info[1]

            cmd = npm+' install --global  %s' % info[0]
            Logs.info(cmd)
            os.system(cmd)

    def copyenv(self):
        "copies a environment"
        req = requirements('python', runtimeonly = self.rtime)
        req.update((i[len('python_'):], j)
                   for i, j in requirements('cpp', runtimeonly = self.rtime).items()
                   if i.startswith('python_'))

        cur  = self.__currentlist()
        chan = {'': {'python': str(cur['python'][0])}}
        for name in req:
            if name == 'python':
                continue

            chan.setdefault(cur[name][1], {})[name] = str(cur[name][0])

        pips = chan.pop('<pip>', [])
        cmd  = ' '.join(i+'='+j for i, j in chan.pop('').items())
        cmd += ' -p '+ self.copy

        self.__run('create '+cmd+' --yes')

        for channel, items in chan.items():
            cmd  = ' '.join(i+'='+j for i, j in items.items())
            cmd += ' -p '+ self.copy + ' -c ' + channel
            self.__run('install ' + cmd + ' --yes')

        if len(pips):
            if sys.platform.startswith('win'):
                path = Path(self.copy)/"Scripts"/"pip.exe"
            else:
                path = Path(self.copy)/"bin"/"pip"
            pippath = str(path.resolve())
            for info in pips.items():
                subprocess.check_call([pippath, 'install', "'%s=%s'" % info])

    def run(self):
        "Installs conda"
        self.__download()
        self.__createenv()
        self.__python_run()
        if not sys.platform.startswith("win"):
            self.__coffee_run()

def condasetup(cnf:Context = None, **kwa):
    "installs / updates a conda environment"
    cset = CondaSetup(cnf.options, **kwa)
    if cset.copy is None:
        cset.run()
    else:
        cset.copyenv()

def condaenv(name, reqs = None, stream = None):
    "creates a conda yaml file"
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
    "runs tests"
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

addmissing(locals())
