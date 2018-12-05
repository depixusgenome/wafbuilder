#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# pylint: disable=protected-access
"Correcting a pylint bug in python 3.7 and pylint <= 2.2.1"
import sys

def _namedtuple_docstring():
    from  pylint.checkers.base import DocStringChecker as _doc
    def _check_docstring(self, node_type, node, *args,
                         __old__ = _doc._check_docstring, **kwa):
        # don't warn about missing-docstring in NamedTuple
        if node_type == 'class' and len(node.bases) == 1 and node.doc is None:
            if node.bases[0].name == 'NamedTuple':
                return
        __old__(self, node_type, node, *args, **kwa)
    _doc._check_docstring = _check_docstring

def _overload():
    def _check(node):
        nodes = getattr(getattr(node, 'decorators', None), 'nodes', [])
        return any(getattr(i, 'name', None) == 'overload' for i in nodes)

    from pylint.checkers.variables import VariablesChecker as _var
    def _check_is_unused(self, name, node, *_, __old__ =  _var._check_is_unused):
        if not _check(node):
            __old__(self, name, node, *_)
    _var._check_is_unused = _check_is_unused

    from pylint.checkers.base  import BasicErrorChecker as _base
    def _check_redefinition(self, redeftype, node, __old__ = _base._check_redefinition):
        if redeftype not in ("method", "function") or not _check(node.parent.frame()[node.name]):
            __old__(self, redeftype, node)
    _base._check_redefinition = _check_redefinition

    import pylint.checkers.classes as _cls
    def overrides_a_method(parent, name, __old__ = _cls.overrides_a_method):
        return _check(parent[name]) or __old__(parent, name)
    _cls.overrides_a_method = overrides_a_method

def _py37_duplicatemro_bug():
    import astroid.scoped_nodes as _nodes

    def _test(name):
        return name[1].startswith('typing._') or name[1] == '.Generic'

    def _verify_duplicates_mro(sequences, cls, context):
        for sequence in sequences:
            names = [(node.lineno, node.qname()) for node in sequence if node.name]
            if len(names) != len(set(names)) and any(_test(j) for j in names):
                for j in range(len(names)-1, 0, -1):
                    if names[j] in names[:j] and _test(names[j]):
                        sequence.pop(j)
                        names.pop(j)

            if len(names) != len(set(names)):
                print(names)
                raise _nodes.exceptions.DuplicateBasesError(
                    message="Duplicates found in MROs {mros} for {cls!r}.",
                    mros=sequences,
                    cls=cls,
                    context=context,
                    )
    _nodes._verify_duplicates_mro = _verify_duplicates_mro

def _py37_class_getitem__():
    import astroid
    import pylint.checkers.utils as _utils
    import pylint.checkers.typecheck as _typecheck
    old = _utils.supports_getitem
    def supports_getitem(value: astroid.node_classes.NodeNG) -> bool:
        if isinstance(value, astroid.ClassDef):
            if _utils._supports_protocol_method(value, "__class_getitem__"):
                return True
            if (
                    value.newstyle
                    and any(
                        i.name == "Generic"
                        or _utils._supports_protocol_method(i, "__class_getitem__")
                        for i in value.mro()
                    )
            ): # typing.Generic
                return True
        return old(value)
    _utils.supports_getitem = supports_getitem
    _typecheck.supports_getitem = supports_getitem

def register(*_):
    "monkeypatch the item"
    _namedtuple_docstring()
    _overload()

    if sys.version_info.major == 3 and sys.version_info.minor == 7:
        _py37_duplicatemro_bug()
        _py37_class_getitem__()
