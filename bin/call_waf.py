#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Calls on waf directly: this is a link which both windows and git can understand"
import  sys
import  subprocess
from    importlib import import_module
from    pathlib   import Path

FNAME = Path.cwd()/"wafbuilder"/"bin"/"waf"
if not FNAME.exists():
    raise IOError(
        "Missing wafbuilder: do\n"
        +"    git submodules update --init --recursive\n"
    )

sys.path.insert(0, "./wafbuilder")
import_module("shellvars").shell(sys.argv, None)

ARGS = tuple(sys.argv)[2 if 'python' in sys.argv[0] else 1:]
if sys.platform.startswith('win'):
    subprocess.run([str(FNAME.with_suffix(".bat"))] + list(ARGS))
else:
    subprocess.run([str(FNAME)] + list(ARGS))
