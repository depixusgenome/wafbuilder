#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"All *basic* python related details"
import subprocess
import urllib.request as request
import tempfile
import os
import sys
import json
from   pathlib              import Path

from   distutils.version    import LooseVersion


from waflib                 import Logs
from waflib.Context         import Context
from .._requirements        import REQ as requirements
from .._cpp                 import Boost

CHANNELS = ['', ' -c conda-forge']

class CondaSetup:
    "installs / updates a conda environment"
    def __init__(self, cnf = None, conda = None, **kwa):
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
        self._conda  = conda if conda else ['conda']

    @staticmethod
    def configure(cnf:Context):
        "get conda script"
        cnf.find_program("conda", var="CONDA", mandatory=True)

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

    def __run(self, cmd):
        try:
            subprocess.check_call(self._conda+cmd.split(' '),
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
        except: # pylint: disable=bare-except
            return True
        return False

    def __read(self, cmd):
        return subprocess.check_output(self._conda+cmd.split(' '),
                                       stderr=subprocess.DEVNULL)

    def __download(self):
        if self.__run('--version'):
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
            pyvers  = '.'.join(str(requirements('python', 'python')).split('.')[:2])
            cmd     = f'create --yes -n {self.envname} python={pyvers} numpy>={version}'
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

        boost = Boost.getlibs()
        if boost:
            itms["boost"] = boost[-1]

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
    cset = CondaSetup(cnf.options, conda = cnf.env['CONDA'], **kwa)
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
