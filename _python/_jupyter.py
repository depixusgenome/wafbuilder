#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"All *basic* python related details"
from .._requirements import REQ as requirements

@requirements.addcheck
def check_python_jupyter(cnf, _, version):
    "checks python's nodejs"
    requirements.programversion(cnf, 'jupyter', version)

_ = None
