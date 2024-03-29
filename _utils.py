#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Default utils for waf"
import inspect
import shutil
from   pathlib      import Path
from typing         import (Iterator, Callable, # pylint: disable=unused-import
                            Iterable, Union, Sequence, Dict, Set, Any, cast, List)
from types          import ModuleType, FunctionType
from functools      import wraps

from waflib.Context   import Context
from waflib.Configure import conf

YES = type('YES', (object,), dict(__doc__ = "Used as a typed enum"))()

def _add(fcn, name : str):
    fname = getattr(fcn, '__func__', fcn).__name__
    return type(fname[0].upper()+fname[1:]+'Make', (Make,), {name: fcn})

def getlocals(glob = None, ind = 1) -> dict:
    "returns locals from an upper frame"
    if isinstance(ind, dict) or isinstance(glob, int):
        ind, glob = glob, ind
    if glob is None:
        return inspect.stack()[ind+1][0].f_locals
    return glob

INCORRECT = [str(Path(__file__).parent)]
ROOT      = str(Path(__file__).parent.parent)
DEFAULT   = str(Path(__file__).parent.parent/"wscript")
def appdir(iframe: int  = None) -> Path:
    "returns directory"
    if iframe is None:
        for frame in inspect.getouterframes(inspect.currentframe()):
            fname = str(Path(frame.filename))
            if fname.startswith('<'):
                continue
            if ((fname.startswith("/") or fname[1:3] == ':\\')
                    and(any(i in fname for i in INCORRECT) or ROOT not in fname)):
                continue
            break
        else:
            if DEFAULT is None:
                for frame in inspect.getouterframes(inspect.currentframe()):
                    print(frame.filename)
                raise AttributeError("Could not find appname frame")

            fname = DEFAULT
    else:
        fname = inspect.getouterframes(inspect.currentframe())[iframe].filename
    if not (fname.startswith("/") or fname[1:3] == ':\\'):
        return cast(Path, Path(ROOT)/fname)
    return cast(Path, Path(fname).parent)

def appname(iframe: int  = None) -> str:
    "returns directory"
    return appdir(iframe).stem

class Make:
    "base class for a given functionnality"
    IS_MAKE = YES

    @classmethod
    def options(cls, opt):
        "Finds all configure methods in child class members"
        run(opt, 'options', makes(cls))

    @classmethod
    def configure(cls, cnf):
        "Finds all configure methods in child class members"
        run(cnf, 'configure', makes(cls))

    @classmethod
    def build(cls, bld):
        "Finds all build methods in child class members"
        run(bld, 'build', makes(cls))

    @classmethod
    def install(cls, bld):
        "Finds all install methods in child class members"
        run(bld, 'install', makes(cls))

def run(item:Context, name:str, elems:Iterable):
    "runs a method to all elements"
    for cls in elems:
        getattr(cls, name, lambda _: None)(item)

def runall(fcn: Callable[[Context], None]):
    """
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
    "gets a list of Makes"
    if isinstance(elems, (type, ModuleType)):
        elems = iter(cls for _, cls in inspect.getmembers(elems))

    elif hasattr(elems, 'items'):
        elems = iter(cls for _, cls in cast(dict, elems).items())

    for cls in elems:
        if cls is not Make and getattr(cls, 'IS_MAKE', None) is YES:
            yield cls

def addconfigure(fcn):
    "adds a configure element to a context"
    return _add(fcn, 'configure')

def addbuild(fcn):
    "adds a build element to a context"
    return _add(fcn, 'build')

def addoptions(fcn):
    "adds an option element to a context"
    return _add(fcn, 'options')

_REC     = 0
_LOADED  = {} # type: Dict[int, Set[Any]]
def loading(cnf, vals):
    "keeps track of loaded items so as not to do the job twice"
    global _REC # pylint: disable=global-statement
    if not isinstance(vals, str):
        _REC += 1
        vals = ' '.join(vals)
        _REC -= 1
    vals = set(vals.split(' ')) - _LOADED.get(id(cnf), set())
    if _REC == 0:
        _LOADED.setdefault(id(cnf), set()).update(vals)
    return ' '.join(vals)

def addmissing(glob = None):
    "adds functions 'load', 'options', 'configure', 'build' if missing from a module"
    glob  = getlocals(glob)
    items = tuple(makes(iter(cls for _, cls in glob.items())))

    def toload(cnf:Context):
        "stacks loads from all basic items"
        global _REC # pylint: disable=global-statement
        _REC += 1
        args = (getattr(cls, 'toload', lambda _:'')(cnf) for cls in items)
        _REC -= 1
        return loading(cnf, args)

    def load(opt:Context):
        "applies load from all basic items"
        outp = glob.get('toload', lambda _: None)(opt)
        if len(outp):
            opt.load(outp)

    def options(opt:Context):
        "applies options from all basic items"
        load(opt)
        run(opt, 'options', items)

    def configure(cnf:Context):
        "applies configure from all basic items"
        load(cnf)
        run(cnf, 'configure', items)

    def build(bld:Context):
        "applies build from all basic items"
        run(bld, 'build', items)

    def install(bld:Context):
        "applies install from all basic items"
        run(bld, 'install', items)

    for val in (load, toload, options, configure, build, install):
        val.__module__ = glob['__name__']
        glob.setdefault(val.__name__, val)

def copyroot(bld:Context, arg):
    "returns the root where items are copied"
    root = bld.bldnode
    return root.make_node(arg) if isinstance(arg, str) else root

def copytargets(bld:Context, arg, items):
    "yields source and targets for copied files"
    root = copyroot(bld, arg)
    for item in items:
        if isinstance(item, tuple):
            # bypass the search
            yield item
            yield from items
            return

        path = Path(str(item))
        if arg  == '':
            tgt = path.name
        else:
            parent = path.parent
            while parent.name != arg:
                parent = parent.parent
            tgt = str(path.relative_to(parent))
        yield (item, root.make_node(tgt))

FILTERS : List[Callable] = []
def copytask(tsk):
    "copies a task, changing css tags when it finds any"
    if not any(act(tsk) for act in FILTERS):
        shutil.copy2(tsk.inputs[0].abspath(),
                     tsk.outputs[0].abspath())

def copyfiles(bld:Context, arg, items:Sequence, install = False):
    "copy py modules to build root path"
    if len(items) == 0:
        return

    if bld.cmd != "build" and install:
        bld.install_files(
                bld.installcodepath(arg, direct = True),
                items,
                cwd            = bld.path,
                relative_trick = True)
        return

    def _kword(_):
        return 'Copying'

    if arg != '':
        copyroot(bld, arg).mkdir()
    for src, tgt in copytargets(bld, arg, items):
        bld(rule        = copytask,
            name        = str(src)+':'+_kword(None).lower(),
            source      = [src],
            target      = [tgt],
            cls_keyword = _kword)

def copyargs(kwa):
    "Copies args to make, discarding some specific to the latter"
    args = dict(kwa)
    for i in ('python_cpp', 'program', 'builders'):
        args.pop(i, None)
    return args

def patch(arg = None, locs = None):
    """
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
    locs = getlocals(locs)
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

CODE_PATH = "code"
@conf
def installpath(*names, direct = False) -> Union[str, Dict[str, str]]:
    "return the install path"
    if names and not isinstance(names[0], str):
        names = names[1:]
    path = '${PREFIX}/'+'/'.join(names)
    return path if direct else {"install_path": path}
@conf
def installcodepath(*names, direct = False) -> Union[str, Dict[str, str]]:
    "return the install path"
    if names and not isinstance(names[0], str):
        names = names[1:]
    return installpath("code", *names, direct = direct)
