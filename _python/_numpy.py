#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"All *basic* python related details"
import subprocess
from waflib.Context     import Context
from .._requirements    import REQ as requirements
from .._utils           import Make
from ._base             import check_python, store, hascompiler

class Numpy(Make):
    "all which concerns numpy"
    @staticmethod
    def configure(cnf:Context):
        "tests numpy and obtains its headers"
        # modules are checked by parsing REQUIRE
        if ('python', 'numpy') not in requirements and hascompiler(cnf):
            return

        check_python(cnf, 'python', requirements.version('python', 'python'))
        cmd = cnf.env.PYTHON[0]                                     \
            + ' -c "from numpy.distutils import misc_util as n;'    \
            + ' print(\'-I\'.join([\'\']+n.get_numpy_include_dirs()))"'
        flg = subprocess.check_output(cmd, shell=True).decode("utf-8")
        store(cnf, flg)
