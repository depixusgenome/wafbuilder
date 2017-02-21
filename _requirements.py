#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Dealing with requirements"
import re
from collections        import OrderedDict
from distutils.version  import LooseVersion
from copy               import deepcopy
from typing             import (Dict, Set, Callable, # pylint: disable=unused-import
                                Optional, Tuple, Iterable)
from waflib.Context     import Context, WSCRIPT_FILE
from ._utils            import appname

class RequirementManager:
    u"Deals with requirements"
    def __init__(self):
        self._checks = OrderedDict() # Dict[str,Dict[str,Callable]]
        self._reqs   = OrderedDict() # Dict[str,Dict[str,Tuple[Optional[str,bool]]]]
        self._done   = False

    def addcheck(self, fcn = None, lang = None, name = None):
        u"adds a means for checking an item"
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

    def require(self, lang = None, name = None, version = None, rtime = True, **kwa):
        u"adds a requirement"
        self._done = False
        if isinstance(lang, str):
            lang = str(lang).lower().replace('cxx', 'cpp')

            if isinstance(name, str):
                name = str(name).lower()
                tmp  = (self._reqs.setdefault(lang, OrderedDict())
                        .setdefault(name, OrderedDict()))
                tmp[appname()] = LooseVersion(str(version)), rtime

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
        u"checks whether the requirements are met"
        if self._done:
            return
        self._done = True

        for lang in self._reqs:
            cnf.load(__package__+'._'+lang)

        defaults = {lang: self._checks[lang].get('default', lambda *x: None)
                    for lang in self._reqs}

        def _get(lang, name):
            version = max(vers for vers, _ in self._reqs[lang][name].values())
            self._checks[lang].get(name, defaults[lang])(cnf, name, version)

        for lang, items in self._reqs.items():
            if lang in items:
                _get(lang, lang)

        for lang, items in self._reqs.items():
            for name in items:
                if name != lang:
                    _get(lang, name)

    def clear(self):
        u"removes all requirements"
        self._reqs.clear()

    def buildonly(self, lang = None):
        u"returns build only dependencies"
        if lang is None:
            return {lang: self.buildonly(lang) for lang in self._reqs}
        else:
            return {name: max(vers for vers, _ in origs.values())
                    for name, origs in self._reqs[lang].items()
                    if not any(isrt for _, isrt in origs.values())}

    def runtime(self, lang = None):
        u"returns build and runtime dependencies"
        if lang is None:
            return {lang: self.runtime(lang) for lang in self._reqs}
        else:
            return {name: max(vers for vers, _ in origs.values())
                    for name, origs in self._reqs[lang].items()
                    if any(isrt for _, isrt in origs.values())}

    def version(self, lang, name = None, allorigs = False):
        u"returns the version of a package"
        if name is None:
            if lang is None:
                return deepcopy(self._reqs)

            return self._reqs.get(lang, None)
        else:
            origs = self._reqs.get(lang, {}).get(name, None)
            if origs is None:
                return None
            elif allorigs:
                return origs
            else:
                return max(vers for vers, _ in origs.values())

    def __contains__(self, args):
        if isinstance(args, str):
            return (args in self._reqs
                    or any(re.match(args, name) for name in self._reqs))
        elif args[0] not in self._reqs:
            return False
        else:
            mods = self._reqs[args[0]]
            return (args[1] in mods
                    or any(re.match(args[1], name) for name in mods))

    @staticmethod
    def programversion(cnf:Context, name:str, minver:LooseVersion, reg = None):
        u"check version of a program"
        if reg is None:
            areg = name
        else:
            areg = reg

        cnf.find_program(name, var = name.upper())
        cmd    = [getattr(cnf.env, name.upper())[0], "--version"]

        found  = cnf.cmd_and_log(cmd).split('\n')
        found  = [line for line in found if len(line)]
        found  = next((line for line in found if areg in line), found[-1]).split()[-1]
        found  = found[found.rfind(' ')+1:].replace(',', '').strip()
        if LooseVersion(found) < minver:
            if reg is None:
                cnf.fatal('The %s version is too old, expecting %r'%(name, minver))
            else:
                cnf.fatal('The %s (%s) version is too old, expecting %r'
                          %(name, str(reg), minver))

    def tostream(self, stream = None):
        u"prints requirements"
        def _print(name, origs, tpe):
            print(' -{:<20}{:<20}{:<}'
                  .format(name, str(max(vers for vers, _ in origs.values())), tpe),
                  file = stream)

        for lang, names in self.version(None).items():
            print('='*15, lang, file = stream)
            for name, origs in names.items():
                if not any(rti  for _, rti in origs.values()):
                    _print(name, origs, 'build')
            for name, origs in names.items():
                if any(rti  for _, rti in origs.values()):
                    _print(name, origs, '')
            print('', file = stream)

    def reload(self, modules):
        u"reloads the data"
        self.clear()
        for mod in modules:
            fname = (mod+"/" if len(mod) else "")+WSCRIPT_FILE
            with open(fname, 'r', encoding = 'utf-8') as stream:
                src = u''.join(stream)
                exec(compile(src, mod, 'exec')) # pylint: disable=exec-used

REQ = RequirementManager()