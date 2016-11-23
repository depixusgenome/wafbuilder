# Project Builder

The module provides a wrapper around *waf* which allows building projects quickly.
A new projects requires:

* A *REQUIRE* file, listing all external libraries and compilers.
* A *wscript* file at the root of the project as well as possibly in all sub-directories to be compiled separatly.

## Checked Coding Rules

Some coding rules are checked when compiling.

### Python
Both 'pylint' and 'mypy' to be available. One can use the [.pylintrc]( https://seafile.picoseq.org/lib/24267447-8840-42b9-981c-b3f0999afb98/file/.pylintrc) for a default configuration

The file encoding is also enforced. The following header is expected on all python script files:

~~~
#! /usr/bin/env python
# encoding: utf-8
~~~

### Cpp
Compilation units should have the '.cc' extension.
A number of warning flags are set automatically. See '_cpp.py'.

## Automations

### C++
*openmp* is detected automatically.
*cppx14* is used automatically.

### Python modules
Modules are compiled and checked using *pylint* and *mypy*.

If a *pybind11* header is included in the c++ sources, the *wafbuilder* will compile a python library as follows:

* there are not .py files in the sources: the library has the name of the directory
* there are .py files in the sources: the python module is created using the .py files
and a '_core' c++ extension is built and added inside the module.

In both cases, the *wafbuilder* expects a function:
~~~
namespace @nsname@ { void pymodule(pybind11::module &); }
~~~
to be implemented somewhere in one of the c++ sources, where *@nsname@* is the directory name.
See '_module.template' for more details.

## The REQUIRE file

This file uses the following format:

~~~
# anything after a '#' is a comment
[PYTHON] # anything beyond this is python related
# First column is the name, second column is the min version, other columns don't matter
python  3.5.2
pandas  0.19.0

[CPP]
clang++ 3.8
g++     4.9
~~~

### When using a conda environment
Using a project-specific conda environment is a swell idea. Obtaining the list of external libraries for python
is then as simple as:
~~~
conda activate my_python_project_env
conda list
~~~

# The wscript file

## Building a single dynamic library or python modules:

Simply add:
~~~
#! /usr/bin/env python
# encoding: utf-8
__import__('wafbuilder').make(locals())
~~~

The *wafbuilder* will set things up automatically.

## Building multiple dynamic libraries:
The following is a good example:
~~~
#!/usr/bin/env python3
# encoding: utf-8
import os
import wafbuilder as builder

# _ALL: the list of sub-directories
_ALL = ('tests',) + tuple(builder.wscripted("src"))

def _recurse(fcn):
    u"helper function for iterating over all directories"
    return builder.recurse(builder, _ALL)(fcn)

def environment(cnf):
    u"prints the environment: use commandline 'python3 waf environment'"
    print(cnf.env)

@_recurse
def options(opt):
    u"Needed by waf, simply calls 'options' in sub-directories'
    pass

@_recurse
def configure(cnf):
    u"Needed by waf, simply calls 'options' in sub-directories'
    pass

@_recurse
def build(bld):
    u"""
    Needed by waf, calls 'options' in sub-directories
    and detects those using pybind11
    """
    builder.findpyext(bld, builder.wscripted('src'))

# the following creates specific build functions for all
# sub-directories. Do 'python3 waf --help' to see this
for item in _ALL:
    builder.addbuild(item, locals())
~~~

