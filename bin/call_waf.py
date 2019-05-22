#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Calls on waf directly: this is a link which both windows and git can understand"
import os
import sys
import subprocess
from   importlib import import_module
from   pathlib   import Path

ARGS = tuple(sys.argv)[2 if 'python' in sys.argv[0] else 1:]

sys.path.insert(0, str(Path(__file__).parent.parent))
import_module("shellvars").shell(sys.argv, None)
os.environ['PREFIX'] = (
    ('patch_' if '--patch' in ARGS else '')
    +import_module("git").version()
)
print("PREFIX="+os.environ['PREFIX'])

FNAME = str(
    (
        Path(__file__).parent/"waf"
    ).with_suffix(".bat" if sys.platform.startswith('win') else "")
)

sys.path.pop(0)
subprocess.run([FNAME, *ARGS])
