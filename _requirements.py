#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Dealing with requirements"
import re
from collections        import OrderedDict
from distutils.version  import LooseVersion
from copy               import deepcopy
from typing             import Dict, List, Callable,  Optional, Tuple, Iterable
from waflib.Context     import Context
from ._defaults         import reload as _reload
from ._utils            import appname

Checks       = Dict[str,Dict[str,Callable]]
Requirements = Dict[str,Dict[str,Tuple[Optional[str],bool]]]
class RequirementManager:
    "Deals with requirements"
    def __init__(self):
        self._checks: Checks       = OrderedDict()
        self._reqs:   Requirements = OrderedDict()
        self._done                 = False

    def addcheck(self, fcn = None, lang = None, name = None):
        "adds a means for checking an item"
        def _wrapper(item, lang = lang, name = name):
            self._done = False
            fname      = item.__name__
            if lang is None:
                assert fname.startswith('check_')
                if fname.count('_') == 1:
                    lang = name = fname.split('_')[-1]
                else:
                    lang,  name = fname.split('_')[1:]

            elif name is None:
                if fname.count('_') == 1:
                    name = lang
                else:
                    name = fname.split('_')[-1]

            lang = str(lang).lower().replace('cxx', 'cpp')
            dic  = self._checks.setdefault(lang, OrderedDict())
            if isinstance(name, (tuple, list)):
                dic.update(dict.fromkeys((i.lower() for i in name), item))
            else:
                dic[name.lower()] = item
            return item

        return _wrapper if fcn is None else _wrapper(fcn)

    def _reqfromlangdict(self, lang, rtime, kwa):
        if lang is None:
            lang = kwa
        else:
            lang.update(kwa)

        for key, vals in lang.items():
            if isinstance(vals, dict):
                vals.setdefault('rtime', rtime)
                self.require(key, vals, rtime = vals.pop('rtime', rtime))

            elif isinstance(vals, (float, int, str)):
                self.require(key, key, vals, rtime = rtime)

            elif len(vals) == 2:
                self.require(key, *vals, rtime = rtime)
            else:
                self.require(key, *vals)

    def _reqfromnamedict(self, lang, name, rtime, kwa):
        if name is None:
            name = kwa
        else:
            name.update(kwa)

        for key, vers in name.items():
            self.require(lang, key, vers, rtime)

    @staticmethod
    def __pinned(origs):
        return any(i[2] for i in origs.values())

    @staticmethod
    def __version(origs):
        pinned = set(str(i[0]) for i in origs.values() if i[2])
        if len(pinned) > 1:
            raise IndexError('Too many pinned versions')
        elif len(pinned):
            return next(iter(pinned))
        else:
            return max(i[0] for i in origs.values())

    def require(self, lang = None, name = None, version = None, rtime = True, **kwa):
        "adds a requirement"
        self._done = False
        if isinstance(lang, str):
            lang = str(lang).lower().replace('cxx', 'cpp')

            if isinstance(name, str):
                name = str(name).lower()
                tmp  = (self._reqs.setdefault(lang, OrderedDict())
                        .setdefault(name, OrderedDict()))

                val  = str(version).strip()
                tmp[appname()] = (LooseVersion(val.replace('=', '')),
                                  rtime,
                                  val.startswith('='))

            elif isinstance(name, Dict):
                self._reqfromnamedict(lang, name, rtime, kwa)

            elif version is not None:
                if len(kwa):
                    raise ValueError()
                elif isinstance(name, Iterable):
                    for i in name:
                        self.require(lang, i, version, rtime)
                else:
                    self.require(lang, lang, version, rtime)
            elif len(kwa):
                self._reqfromnamedict(lang, kwa, rtime, {})
            else:
                raise TypeError()

        elif {name, version} != {None}:
            raise TypeError()

        else:
            self._reqfromlangdict(lang, rtime, kwa)

    def check(self, cnf):
        "checks whether the requirements are met"
        if self._done:
            return
        self._done = True

        for lang in self._reqs:
            cnf.load(__package__+'._'+lang)

        defaults = {lang: self._checks[lang].get('default', lambda *x: None)
                    for lang in self._reqs}

        def _get(lang, name):
            version = max(vers[0] for vers in self._reqs[lang][name].values())
            self._checks[lang].get(name, defaults[lang])(cnf, name, version)

        for lang, items in self._reqs.items():
            if lang in items:
                _get(lang, lang)

        for lang, items in self._reqs.items():
            for name in items:
                if name != lang:
                    _get(lang, name)

    def clear(self):
        "removes all requirements"
        self._reqs.clear()

    def buildonly(self, lang = None):
        "returns build only dependencies"
        if lang is None:
            return {lang: self.buildonly(lang) for lang in self._reqs}
        return {name: self.__version(origs)
                for name, origs in self._reqs[lang].items()
                if not any(isrt for _1, isrt, _2 in origs.values())}

    def runtime(self, lang = None):
        "returns build and runtime dependencies"
        if lang is None:
            return {lang: self.runtime(lang) for lang in self._reqs}
        return {name: self.__version(origs)
                for name, origs in self._reqs[lang].items()
                if any(isrt for _1, isrt, _2 in origs.values())}

    def __call__(self, lang = None, name = None, runtimeonly = False):
        "returns build and runtime dependencies"
        if runtimeonly and name is None:
            return self.runtime(lang)
        if lang is None:
            assert name is None
            return {lang: self(lang) for lang in self._reqs}
        if name is None:
            return {name: self.__version(origs)
                    for name, origs in self._reqs[lang].items()}
        return self.__version(self._reqs[lang][name])

    def version(self, lang, name = None, allorigs = False):
        "returns the version of a package"
        if name is None:
            if lang is None:
                return deepcopy(self._reqs)

            val = self._reqs.get(lang, None)
            if val is None:
                return None
            ret: Requirements = OrderedDict()
            for k, origs in val.items():
                ret[k] = OrderedDict((i, j[:2]) for i, j in origs.items())
            return ret
        origs = self._reqs.get(lang, {}).get(name, None)
        if origs is None:
            return None
        if allorigs:
            return {i:j[:2] for i, j in origs.items()}
        return self.__version(origs)

    def pinned(self, lang = None, name = None):
        "returns pinned packages"
        if name is None:
            if lang is None:
                ret: List = []
                for i in self._reqs:
                    ret.extend(self.pinned(i))
                return ret

            val = self._reqs.get(lang, None)
            if val is None:
                return []
            return [i for i, origs in val.items() if self.__pinned(origs)]
        origs = self._reqs.get(lang, {}).get(name, None)
        return origs is not None and self.__pinned(origs)

    def __contains__(self, args):
        if isinstance(args, str):
            return (args in self._reqs
                    or any(re.match(args, name) for name in self._reqs))
        if args[0] not in self._reqs:
            return False

        mods = self._reqs[args[0]]
        return (args[1] in mods
                or any(re.match(args[1], name) for name in mods))

    @staticmethod
    def programversion(cnf   :Context,
                       name  :str,
                       minver:LooseVersion,
                       reg       = None,
                       mandatory = True):
        "check version of a program"
        if reg is None:
            areg = name
        else:
            areg = reg

        try:
            cnf.find_program(name, var = name.upper())
        except: # pylint: disable=bare-except
            if mandatory:
                raise
            else:
                return False

        cmd    = [getattr(cnf.env, name.upper())[0], "--version"]

        found  = cnf.cmd_and_log(cmd).split('\n')
        found  = [line for line in found if len(line)]
        found  = next((line for line in found if areg in line), found[-1]).split()[-1]
        found  = found[found.rfind(' ')+1:].replace(',', '').strip()
        if found.startswith('v'):
            found = found[1:]

        if LooseVersion(found) < minver:
            if not mandatory:
                return False
            if reg is None:
                cnf.fatal('The %s version is too old, expecting %r'%(name, minver))
            else:
                cnf.fatal('The %s (%s) version is too old, expecting %r'
                          %(name, str(reg), minver))
        return True

    def tostream(self, stream = None):
        "prints requirements"
        def _print(name, origs, tpe):
            vers = str(self.__version(origs))
            if self.__pinned(origs):
                vers = '='+vers
            print(' -{:<20}{:<20}{:<}'.format(name, vers, tpe), file = stream)

        for lang, names in self.version(None).items():
            print('='*15, lang, file = stream)
            for name, origs in names.items():
                if not any(rti  for _1, rti, _2 in origs.values()):
                    _print(name, origs, 'build')
            for name, origs in names.items():
                if any(rti  for _1, rti, _2 in origs.values()):
                    _print(name, origs, '')
            print('', file = stream)

    def reload(self, modules, clear = True):
        "reloads the data"
        if clear:
            self.clear()
        _reload(modules)

REQ = RequirementManager()
