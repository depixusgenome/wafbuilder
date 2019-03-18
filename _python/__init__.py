#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"All *basic* python related details"
from ._conda    import condasetup, condaenv, CHANNELS
from ._pybind11 import findpyext
from ._linting  import checkpy
from ._pytest   import PyTesting
from ._jupyter  import _
from ._script   import (IS_MAKE,  # pylint: disable=no-name-in-module
                        options, configure, load, build, toload)
