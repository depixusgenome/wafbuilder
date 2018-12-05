#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"Correcting a pylint bug in python 3.7 and pylint <= 2.2.1"
import sys

def register(*_):
    "monkeypatch the item"
    import astroid
    import pylint.checkers.base as _base
    old = _base.DocStringChecker._check_docstring
    def _check_docstring(self, node_type, node, *args, **kwa):
        # don't warn about missing-docstring in NamedTuple
        if node_type == 'class' and len(node.bases) == 1 and node.doc is None:
            if node.bases[0].name == 'NamedTuple':
                return 
        return old(self, node_type, node, *args, **kwa)
    _base.DocStringChecker._check_docstring = _check_docstring

    if sys.version_info.major == 3 and sys.version_info.minor == 6:
        return
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
