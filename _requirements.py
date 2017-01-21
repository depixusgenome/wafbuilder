#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Dealing with requirements"
from distutils.version  import LooseVersion
from typing             import (Dict, Set, Callable, # pylint: disable=unused-import
                                Optional, Tuple, Iterable)
from collections        import OrderedDict

class RequirementManager:
    u"Deals with requirements"
    def __init__(self):
        self._checks = OrderedDict() # Dict[str,Dict[str,Callable]]
        self._reqs   = OrderedDict() # Dict[str,Dict[str,Tuple[Optional[str,bool]]]]
        self._done   = False

    def requirementcheck(self, fcn = None, lang = None, name = None):
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
                name      = str(name).lower()
                tmp       = self._reqs.setdefault(lang, OrderedDict())
                tmp[name] = str(version), rtime

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
            for name, (version, _1) in items.items():
                fcns.get(name, default)(cnf, name, version)

    def buildonly(self):
        u"returns build only dependencies"
        return {lang: {name: version for name, (version, isrt) in mods.items() if not isrt}
                for lang, mods in self._reqs.items()}

    def runtime(self):
        u"returns build and runtime dependencies"
        return {lang: {name: version for name, (version, isrt) in mods.items() if isrt}
                for lang, mods in self._reqs.items()}

    def version(self, lang, name = None):
        u"returns the version of a package"
        if name is None:
            return self._reqs.get(lang, None)
        else:
            return self._reqs.get(lang, {}).get(name, [None])[0]

    def __contains__(self, args):
        if isinstance(args, str):
            return args in self._reqs
        else:
            return args[1] in self._reqs.get(args[0], tuple())

def checkprogramversion(cnf, name, minver):
    u"check version of a program"
    cnf.find_program(name, var = name.upper())
    cmd    = [getattr(cnf.env, name.upper())[0], "--version"]
    found  = cnf.cmd_and_log(cmd).split('\n')
    found  = next((line for line in found if name in line.lower()), found[-1]).split()[-1]
    found  = found[found.rfind(' ')+1:].replace(',', '').strip()
    if LooseVersion(found) < LooseVersion(minver):
        cnf.fatal('The %s version is too old, expecting %r'%(name, minver))

_REQ = RequirementManager()

def requiredversion(lang, name = None):
    u"whether an element is required"
    return _REQ.version(lang, name)

def isrequired(lang, name = None):
    u"whether an element is required"
    if name is None:
        return lang in _REQ
    else:
        return (lang, name) in _REQ

def requirementcheck(fcn = None, lang = None, name = None):
    u"adds a means for checking an item"
    return _REQ.requirementcheck(fcn, lang, name)

def require(lang = None, name = None, version = None, rtime = True, **kwa):
    u"adds a requirement"
    return _REQ.require(lang, name, version, rtime, **kwa)

def check(cnf):
    u"checks whether the requirements are met"
    return _REQ.check(cnf)

def buildonly():
    u"returns build only dependencies"
    return _REQ.buildonly()

def runtime():
    u"returns build and runtime dependencies"
    return _REQ.runtime()
