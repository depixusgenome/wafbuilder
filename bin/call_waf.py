#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Calls on waf directly: this is a link which both windows and git can understand"
import  sys
import  subprocess
from    importlib import import_module
from    pathlib   import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import_module("shellvars").shell(sys.argv, None)
sys.path.pop(0)

ARGS  = tuple(sys.argv)[2 if 'python' in sys.argv[0] else 1:]
FNAME = str(
    (
        Path(__file__).parent/"waf"
    ).with_suffix(".bat" if sys.platform.startswith('win') else "")
)
subprocess.run([FNAME, *ARGS])
