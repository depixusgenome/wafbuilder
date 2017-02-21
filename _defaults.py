#l!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Default functions for waf"
import os
from typing     import Sequence, Dict # pylint: disable=unused-import
from functools  import wraps
from waflib.Context import WSCRIPT_FILE

_DEFAULT_WAFS = {} # type: Dict[str, str]

def wscripted(path) -> Sequence[str]:
    u"return subdirs with wscript in them"
    path = path.replace("\\", "/")
    if not path.endswith("/"):
        path += "/"
    return [path+x for x in os.listdir(path)
            if (os.path.exists(path+x+"/"+WSCRIPT_FILE)
                or os.path.abspath(path+x)+"/"+WSCRIPT_FILE in _DEFAULT_WAFS)]

def defaultwscript(path, code = 'make()'):
    u"""
    Defines default wscripts for all children in a directory.
    This is dynamic.
    """
    import waflib.Utils as _Utils
    if not getattr(_Utils, '__wafbuilder_monkeypatch__', False):
        _Utils.__wafbuilder_monkeypatch__ = True

        @wraps(_Utils.readf)
        def _read(fname, *args, __old__ = _Utils.readf, **kwa):
            code = _DEFAULT_WAFS.get(fname.replace("\\", "/"), None)
            if code is not None and not os.path.exists(fname):
                return code
            return __old__(fname, *args, **kwa)
        _Utils.readf = _read

        from waflib.Node import Node
        @wraps(Node.exists)
        def _exists(self, *_, __old__ = Node.exists):
            if self.abspath().replace("\\", "/") in _DEFAULT_WAFS:
                return True
            else:
                return __old__(self)
        Node.exists = _exists

    path = path.replace("\\", "/")
    if not path.endswith("/"):
        path += "/"

    dirs = [os.path.abspath(path+x)+"/"+WSCRIPT_FILE for x in os.listdir(path)]
    _DEFAULT_WAFS.update((i, code) for i in dirs)

def reload(modules):
    u"reloads the data"
    for mod in modules:
        fname = os.path.abspath((mod+"/" if len(mod) else ""))+"/"+WSCRIPT_FILE
        if os.path.exists(fname):
            with open(fname, 'r', encoding = 'utf-8') as stream:
                src = u''.join(stream)
                exec(compile(src, mod, 'exec')) # pylint: disable=exec-used

        elif fname in _DEFAULT_WAFS:
            exec(compile(src, mod, 'exec')) # pylint: disable=exec-used

        else:
            raise IOError("missing wscript: " + fname)
