#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Dealing with requirements"
from distutils.version  import LooseVersion
from copy               import deepcopy
from typing             import (Dict, Set, Callable, # pylint: disable=unused-import
                                Optional, Tuple, Iterable)
from waflib.Context     import Context, WSCRIPT_FILE
from collections        import OrderedDict
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

        for lang, items in self._reqs.items():
            fcns    = self._checks[lang]
            default = fcns.get('default', lambda *x: None)
            for name, origs in items.items():
                version = max(vers for vers, _ in origs.values())
                fcns.get(name, default)(cnf, name, version)

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
            return args in self._reqs
        else:
            return args[1] in self._reqs.get(args[0], tuple())

    @staticmethod
    def programversion(cnf:Context, name:str, minver:LooseVersion):
        u"check version of a program"
        cnf.find_program(name, var = name.upper())
        cmd    = [getattr(cnf.env, name.upper())[0], "--version"]
        found  = cnf.cmd_and_log(cmd).split('\n')
        found  = next((line for line in found if name in line.lower()), found[-1]).split()[-1]
        found  = found[found.rfind(' ')+1:].replace(',', '').strip()
        if LooseVersion(found) < minver:
            cnf.fatal('The %s version is too old, expecting %r'%(name, minver))

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
