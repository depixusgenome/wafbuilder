#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Default utils for waf"
import inspect
import shutil
from typing         import (Iterator, Callable, # pylint: disable=unused-import
                            Iterable, Union, Sequence, cast)
from types          import ModuleType, FunctionType
from functools      import wraps

from waflib.Context import Context

YES = type('YES', (object,), dict(__doc__ = u"Used as a typed enum"))()

def _add(fcn, name : str):
    fname = getattr(fcn, '__func__', fcn).__name__
    return type(fname[0].upper()+fname[1:]+'Make', (Make,), {name: fcn})

def getlocals(glob = None, ind = 1) -> dict:
    u"returns locals from an upper frame"
    if isinstance(ind, dict) or isinstance(glob, int):
        ind, glob = glob, ind
    if glob is None:
        return inspect.stack()[ind+1][0].f_locals
    return glob

def appname(iframe: int  = None) -> str:
    u"returns directory"
    if iframe is None:
        mymod  = __file__.replace('\\', '/')
        mymod  = mymod[:mymod.rfind('/')]
        myroot = mymod[:mymod.rfind('/')]
        for frame in inspect.getouterframes(inspect.currentframe()):
            fname = frame.filename.replace('\\', '/')
            if fname.startswith('<') or mymod in fname:
                continue
            if myroot not in fname:
                continue
            break
        else:
            raise AttributeError("Could not find appname frame")

    else:
        fname = inspect.getouterframes(inspect.currentframe())[iframe].filename
    fname = fname.replace('\\', '/')
    fname = fname[:fname.rfind('/')]
    return fname[fname.rfind('/')+1:]

class Make(object):
    u"base class for a given functionnality"
    IS_MAKE = YES

    @classmethod
    def options(cls, opt):
        u"Finds all configure methods in child class members"
        run(opt, 'options', makes(cls))

    @classmethod
    def configure(cls, cnf):
        u"Finds all configure methods in child class members"
        run(cnf, 'configure', makes(cls))

    @classmethod
    def build(cls, bld):
        u"Finds all build methods in child class members"
        run(bld, 'build', makes(cls))

def run(item:Context, name:str, elems:Iterable):
    u"runs a method to all elements"
    for cls in elems:
        getattr(cls, name, lambda _: None)(item)

def runall(fcn: Callable[[Context], None]):
    u"""
    decorator for calling all Make objects after the decorated function.

    usage:

    >> class MyMake(Make):
    >>    @staticmethod
    >>    def configure(cnf):
    >>       print("this happens later")
    >>
    >> @runall
    >> def configure(cnf):
    >>    print("this happens first")
    """
    if not isinstance(fcn, FunctionType):
        raise TypeError('{} should be a function'.format(fcn))

    mod = inspect.getmodule(fcn)

    @wraps(cast(Callable, fcn))
    def _wrapper(cnf:Context):
        fcn(cnf)
        run(cnf, fcn.__name__, makes(mod))

    return _wrapper

def makes(elems:'Union[Iterable,dict,type,ModuleType]') -> 'Iterator[type]':
    u"gets a list of Makes"
    if isinstance(elems, (type, ModuleType)):
        elems = iter(cls for _, cls in inspect.getmembers(elems))

    elif hasattr(elems, 'items'):
        elems = iter(cls for _, cls in cast(dict, elems).items())

    for cls in elems:
        if cls is not Make and getattr(cls, 'IS_MAKE', None) is YES:
            yield cls

def addconfigure(fcn):
    u"adds a configure element to a context"
    return _add(fcn, 'configure')

def addbuild(fcn):
    u"adds a build element to a context"
    return _add(fcn, 'build')

def addoptions(fcn):
    u"adds an option element to a context"
    return _add(fcn, 'options')

_REC     = 0
_LOADED  = {}
def loading(cnf, vals):
    "keeps track of loaded items so as not to do the job twice"
    global _REC
    if not isinstance(vals, str):
        _REC += 1
        vals = ' '.join(vals)
        _REC -= 1
    vals = set(vals.split(' ')) - _LOADED.get(id(cnf), set())
    if _REC == 0:
        _LOADED.setdefault(id(cnf), set()).update(vals)
    return ' '.join(vals)

def addmissing(glob = None):
    u"adds functions 'load', 'options', 'configure', 'build' if missing from a module"
    glob  = getlocals(glob)
    items = tuple(makes(iter(cls for _, cls in glob.items())))

    def toload(cnf:Context):
        u"stacks loads from all basic items"
        global _REC
        _REC += 1
        args = (getattr(cls, 'toload', lambda:'')(cnf) for cls in items)
        _REC -= 1
        return loading(cnf, args)

    def load(opt:Context):
        u"applies load from all basic items"
        outp = glob.get('toload', lambda _: None)(opt)
        if len(outp):
            opt.load(outp)

    def options(opt:Context):
        u"applies options from all basic items"
        load(opt)
        run(opt, 'options', items)

    def configure(cnf:Context):
        u"applies configure from all basic items"
        load(cnf)
        run(cnf, 'configure', items)

    def build(bld:Context):
        u"applies build from all basic items"
        run(bld, 'build', items)

    for val in (load, toload, options, configure, build):
        val.__module__ = glob['__name__']
        glob.setdefault(val.__name__, val)

def copyroot(bld:Context, arg):
    u"returns the root where items are copied"
    return bld.bldnode.make_node(arg) if isinstance(arg, str) else arg

def copytargets(bld:Context, arg, items):
    u"yields source and targets for copied files"
    root = copyroot(bld, arg)
    for item in items:
        tgt = item.abspath().replace('\\', '/')
        tgt = tgt[tgt.rfind('/'+arg+'/')+2+len(arg):]
        yield (item, root.make_node(tgt))

def copyfiles(bld:Context, arg, items:Sequence):
    u"copy py modules to build root path"
    if len(items) == 0:
        return

    def _cpy(tsk):
        shutil.copy2(tsk.inputs[0].abspath(),
                     tsk.outputs[0].abspath())
    def _kword(_):
        return 'Copying'

    copyroot(bld, arg).mkdir()
    for src, tgt in copytargets(bld, arg, items):
        bld(rule        = _cpy,
            name        = str(src)+':'+_kword(None).lower(),
            source      = [src],
            target      = [tgt],
            cls_keyword = _kword)

def copyargs(kwa):
    u"Copies args to make, discarding some specific to the latter"
    args = dict(kwa)
    for i in ('python_cpp', 'program', 'builders'):
        args.pop(i, None)
    return args

def patch(arg = None, locs = None):
    u"""
    patches a function already in locs.
    For example:

    >>> def configure(cnf):
    >>>     print('this happens in between')
    >>>
    >>> @patch
    >>> def configure(cnf):
    >>>     print('this happens last!')
    >>>
    >>> @patch('postfix')
    >>> def configure(cnf):
    >>>     print('this happens last!')
    >>>
    >>> @patch
    >>> def postfix_configure(cnf):
    >>>     print('this happens last!')
    >>>
    >>> @patch('prefix')
    >>> def configure(cnf):
    >>>     print('this happens first!')
    >>>
    >>> @patch
    >>> def prefix_configure(cnf):
    >>>     print('this happens first!')
    """
    locs = getlocals()
    def _wrapper(fcn):
        name = fcn.__name__
        pre  = name.startswith('pre_') or name.startswith('prefix_')
        if pre and (str(arg).lower() == 'postfix'):
            raise KeyError("incompatible requests")

        post = name.startswith('post_') or name.startswith('postfix_')
        if post and (str(arg).lower() == 'prefix'):
            raise KeyError("incompatible requests")

        if pre or str(arg).lower() == 'prefix':
            if name.startswith('pre_') or name.startswith('prefix_'):
                name = name[name.find('_')+1:]
            old  = locs.pop(name)

            @wraps(fcn)
            def _pre_wrapped(*args, **kwa):
                fcn(*args, **kwa)
                return old(*args, **kwa)

            locs[name] = _pre_wrapped
        else:
            if name.startswith('post_') or name.startswith('postfix_'):
                name = name[name.find('_')+1:]
            old  = locs.pop(name)

            @wraps(fcn)
            def _post_wrapped(*args, **kwa):
                old(*args, **kwa)
                return fcn(*args, **kwa)

            locs[name] = _post_wrapped
        return fcn

    if callable(arg):
        return _wrapper(arg)
    return _wrapper
