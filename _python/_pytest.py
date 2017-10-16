#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"All *basic* python related details"
from ._pybind11 import pymoduledependencies

def runtest(bld, *names):
    "runs tests"
    pyext = set(bld.env.pyextmodules)
    def _scan(_):
        deps  = list(pymoduledependencies(names, None) & pyext)
        nodes = [bld.get_tgen_by_name(dep+':pyext').tasks[-1].outputs[0] for dep in deps]
        return (nodes, [])

    bld(source      = names,
        name        = 'pytests',
        always      = True,
        color       = 'YELLOW',
        rule        = '${PYTHON} -m pytest ${SRC} ',
        scan        = _scan,
        cls_keyword = lambda _: 'Pytest')
