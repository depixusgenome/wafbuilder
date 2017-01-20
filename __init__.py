#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Default functions for waf"
import os
from typing     import Sequence, Callable
from functools  import wraps

from waflib.Context import Context
from waflib.Build   import BuildContext

from ._requirements import require, check as _checkrequirements
from ._utils        import addmissing, appname, copyfiles, runall
from ._python       import checkpy, findpyext
from .              import _git as gitinfo

def wscripted(path) -> Sequence[str]:
    u"return subdirs with wscript in them"
    path = path.replace("\\", "/")
    if not path.endswith("/"):
        path += "/"
    return [path+x for x in os.listdir(path) if os.path.exists(path+x+"/wscript")]

def top()-> str:
    u"returns top path"
    path = __file__[:__file__.rfind("/")]
    path = path    [:path       .rfind("/")]
    return path+"/"

def output() -> str:
    u"returns build path"
    return top() + "/build"

def version() -> str:
    u"returns git tag"
    try:
        return gitinfo.version()
    except:             # pylint: disable=bare-except
        return "0.0.1"

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

def addbuild(name:str, glob:dict):
    u"Registers a command from a child wscript"
    def _fcn(bld):
        bld.recurse(name)
    _fcn.__doc__  = u'Build module "{}"'.format(name)
    ldoc          = len(_fcn.__doc__)
    _fcn.__name__ = 'build_'+name[(name.rfind('/')+1) if '/' in name else 0:]

    def _doc(path):
        if not os.path.exists(path):
            return
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

def make(glob, **kw):
    u"sets default values to wscript global variables"
    def options(*_):
        u"does nothing"
        for name in kw.get("builders", ['py']):
            try:
                __import__(__name__+'.'+name)
            except ImportError:
                pass

    def configure(cnf:Context):
        u"configures a python module"
        for name in kw.get("builders", ['py']):
            getattr(cnf, 'configure_'+name, lambda: None)()

    def build(bld:Context):
        u"builds a python module"
        app  = glob['APPNAME']
        vers = glob['VERSION']
        kwa  = dict(kw)
        kwa .pop('builders', None)
        for name in kw.get("builders", ['py']):
            getattr(bld, 'build_'+name)(app, vers, **kwa)

    # pylint: disable=unnecessary-lambda
    toadd = dict(VERSION   = lambda: version(),
                 APPNAME   = lambda: appname(),
                 top       = lambda: ".",
                 out       = lambda: output(),
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
def configure(cnf:Context, __old__ = locals().pop('configure')):
    u"Default configure"
    __old__(cnf)
    _checkrequirements(cnf)

__builtins__['make']    = make
__builtins__['require'] = require
