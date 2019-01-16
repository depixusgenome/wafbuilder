#l!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Default functions for waf"
import os
from pathlib        import Path
from typing         import Sequence, Dict # pylint: disable=unused-import
from functools      import wraps
from waflib.Context import WSCRIPT_FILE

_DEFAULT_WAFS = {} # type: Dict[Path, str]

def wscripted(path) -> Sequence[str]:
    u"return subdirs with wscript in them"
    if isinstance(path, (tuple, list, set, frozenset)):
        return sum((wscripted(i) for i in path), [])
    orig = path
    path = Path.cwd() / path
    return [orig+'/'+x for x in os.listdir(str(path))
            if ((path/x/WSCRIPT_FILE).exists()
                or (path/x).resolve()/WSCRIPT_FILE in _DEFAULT_WAFS)]

def defaultwscript(path, code = 'make(locals())'):
    u"""
    Defines default wscripts for all children in a directory.
    This is dynamic.
    """
    import waflib.Utils as _Utils
    if not getattr(_Utils, '__wafbuilder_monkeypatch__', False):
        _Utils.__wafbuilder_monkeypatch__ = True

        @wraps(_Utils.readf)
        def _read(fname, *args, __old__ = _Utils.readf, **kwa):
            code = _DEFAULT_WAFS.get(Path(fname), None)
            if code is not None and not os.path.exists(fname):
                return code
            return __old__(fname, *args, **kwa)
        _Utils.readf = _read

        from waflib.Node import Node
        @wraps(Node.exists)
        def _exists(self, *_, __old__ = Node.exists):
            if Path(self.abspath()) in _DEFAULT_WAFS:
                return True
            return __old__(self)
        Node.exists = _exists

    path = Path.cwd()/path
    dirs = [(path/x).resolve()/WSCRIPT_FILE for x in os.listdir(str(path))
            if x[0] not in ('.', '_')]
    _DEFAULT_WAFS.update((i, code) for i in dirs)

def reload(modules):
    u"reloads the data"
    for mod in modules:
        fname = (Path.cwd()/mod).resolve()/WSCRIPT_FILE

        if fname.exists():
            with open(str(fname), 'r', encoding = 'utf-8') as stream:
                src = u''.join(stream)
                exec(compile(src, mod, 'exec')) # pylint: disable=exec-used

        elif fname in _DEFAULT_WAFS:
            src = _DEFAULT_WAFS[fname]
            exec(compile(src, mod, 'exec')) # pylint: disable=exec-used

        else:
            raise IOError("missing wscript: " + fname)
