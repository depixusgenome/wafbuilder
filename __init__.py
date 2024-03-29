#l!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Default functions for waf"
import os
from typing     import Sequence, Callable, Optional, Dict # pylint: disable=unused-import
from pathlib    import Path
from functools  import wraps

from waflib.Context import Context
from waflib.Build   import BuildContext
from waflib.Configure       import conf

from ._defaults     import wscripted, defaultwscript
from ._requirements import REQ as requirements, OPT as suggested
from ._utils        import (
    addmissing, appname, appdir, copyfiles,
    runall, patch, getlocals, copyroot, FILTERS,
    CODE_PATH
)
from ._python       import (
    checkpy, findpyext, condaenv, condasetup, CHANNELS,
    PyTesting
)
from .git           import version

def register(name:str, fcn:Callable[[Context], None], glob:dict):
    u"Registers a *build* command for building a single module"
    # register a command for building a single module
    type(name.capitalize()+'BuildContext', (BuildContext,),
         {'cmd': 'build_'+name , 'fun': 'build_'+name},)

    def _single(bld:BuildContext):
        u"runs a single src module"
        print("building single element: ", glob['APPNAME'])
        fcn(bld)

    glob['build_'+name] = _single

def addbuild(name:str, glob:Optional[dict] = None):
    u"Registers a command from a child wscript"
    glob = getlocals(glob)
    if isinstance(name, (tuple, list)):
        for i in name:
            addbuild(i, glob)
        return

    def _fcn(bld):
        bld.recurse(name)
    _fcn.__doc__  = u'Build module "{}"'.format(name)
    ldoc          = len(_fcn.__doc__)
    _fcn.__name__ = 'build_'+name[(name.rfind('/')+1) if '/' in name else 0:]

    def _doc(path):
        if not os.path.exists(path):
            return None
        with open(path, "r") as stream:
            bnext = False
            for line in stream:
                if bnext:
                    if '.' in line:
                        line = line[:line.rfind('.')]
                    _fcn.__doc__  += u": " + line.strip()
                    break
                if line.startswith('u"""'):
                    bnext = True
                elif line.startswith('u"'):
                    _fcn.__doc__  += u": " + line[2:-2].strip()
                    break
        return ldoc < len(_fcn.__doc__)

    if not _doc(name+'/wscript'):
        _doc(name+'/__init__.py')

    _fcn.__name__ = 'build_'+name[(name.rfind('/')+1) if '/' in name else 0:]
    glob[_fcn.__name__] = _fcn

_DEFAULT = ['python']
def default(*args):
    "Sets the default builder(s) to use: cpp, py or coffee or typescript"
    _DEFAULT.clear()
    _DEFAULT.extend(args)

def make(glob = None, **kw):
    u"sets default values to wscript global variables"
    glob = getlocals(glob)

    def _get(name):
        name = name.lower()
        return 'cpp' if name == 'cxx' else ('python' if name == 'py' else name)

    def options(*_):
        u"does nothing"
        for name in kw.get("builders", _DEFAULT):
            __import__(__name__+'._'+_get(name))

    def configure(cnf:Context): # pylint: disable=redefined-outer-name
        u"configures a python module"
        for name in kw.get("builders", _DEFAULT):
            getattr(cnf, 'configure_'+_get(name), lambda: None)()

    def build(bld:Context):
        u"builds a python module"
        app  = glob['APPNAME']
        vers = glob['VERSION']
        kwa  = dict(kw)
        kwa .pop('builders', None)
        spe  = {
            name: kwa.pop(name, {})
            for name in kw.get("builders", _DEFAULT)
        }
        for name in kw.get("builders", _DEFAULT):
            (
                getattr(bld, 'build_'+_get(name))
                (app, vers, **dict(kwa, **spe.get(name, {})))
            )

    # pylint: disable=unnecessary-lambda
    toadd = dict(VERSION   = lambda: version(appdir()),
                 APPNAME   = lambda: appname(),
                 options   = lambda: options,
                 configure = lambda: configure,
                 build     = lambda: build)

    for key, fcn in toadd.items():
        if key not in glob:
            glob[key] = fcn()

    if glob['APPNAME'] not in glob:
        register(glob['APPNAME'], glob['build'], glob)

def recurse(builder, items):
    u"runs over relative path to child wscripts"
    def _wrapper(fcn):
        @wraps(fcn)
        def _wrap(bld):
            getattr(builder, fcn.__name__)(bld)
            fcn(bld)
            for item in items:
                bld.recurse(item)
        return _wrap
    return _wrapper

addmissing(locals())

@patch('postfix', locals())
def configure(cnf:Context):
    u"Default configure"
    requirements.check(cnf)

# pylint: disable=invalid-name
make    = make                  # type: ignore
require = requirements.require  # type: ignore
suggest = suggested.require     # type: ignore

__builtins__.update(
    make    = make,    # type: ignore
    require = require, # type: ignore
    suggest = suggest, # type: ignore
    patch   = patch    # type: ignore
)
