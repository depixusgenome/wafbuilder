# Project Builder

The module provides a wrapper around *waf* which allows building projects quickly.
A new projects requires:

* requirement management
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

### Coffeescript
Compilation is performed automatically provided the extension used is '.coffee'.
The output has the extension '.js'. The '.coffee' file is also copied together
with the '.py' files. In order to activate the coffeescript support,
one must define it in the list of builders (see wscript file description).


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

The '.py' and '.ipynb' files are copied to the build directory such that the python module
can be imported from there.

## The Requirement management

A *require* function is available as a builtin (no imports).
One calls it within a *wscript* file, providing:
    
1. a language: python, cpp or coffee
2. a package name: numpy, nlopt, boost_math, ...
3. a version: '1.1.1', ...
4. whether it is runtime only or not.

The code would look like:

~~~
# no package name provided: the name is defaulted to the language
# the version is a float but could be a string
require(python = 3.5, rtime = True)

# provide package names using keyword arguments
require('python', numpy = '1.11.1', pandas = 3.2, rtime = True)

# provide one package name only
require('cpp', 'g++', 5.6, False)

# provide one a list of package names with the same version for all
require('cpp', ('boost_math', 'boost_accumulators'),  1.60, False)
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
make()
~~~

The *wafbuilder* will set things up automatically.

## Adding coffeescript support

The file then looks like:
~~~
make(builders = ['py', 'coffee'])
~~~

The *configure* function will look for coffeescript and check its version. The 
minimum version must be defined in the requirements.

The *builders* list specifies that this directory contains both python, possibly cpp,
as well as coffeescript files.

## Building multiple dynamic libraries:
Consider a project with sub-directories:

* *src*: a directory containing one sub-directory per python module or c++ library.
* *tests*: all test files.

The following *wscript* will build the sources and tests:

~~~
#!/usr/bin/env python3
# encoding: utf-8
import wafbuilder as builder

# add minimum version for c++
require(cxx    = {'msvc'     : 14.0,
                  'clang++'  : 3.8,
                  'g++'      : 5.4},
        rtime = False)

# add minimum version for python as well as some basic modules
require(python = {'python': 3.5, 'numpy': '1.11.2', 'pandas': '0.19.0'},
        rtime  = True)

# add minimum version for python as well as some basic modules,
# needed only for building
require(python = {'pybind11' : '2.0.1',
                  'pylint'   : '1.5.4',
                  'pytest'   : '3.0.4',
                  'mypy'     : '0.4.4'},
        rtime  = False)

# _ALL: the list of sub-directories
_ALL = ('tests',) + tuple(builder.wscripted("src"))

def options(opt):
    u"Needed by waf, simply calls 'options' in sub-directories'
    builder.options(opt)
    for item in _ALL:
        opt.recurse(item)

def configure(cnf):
    u"Needed by waf, simply calls 'configure' in sub-directories'
    builder.configure(cnf)
    for item in _ALL:
        cnf.recurse(item)

def build(bld):
    u"""
    Needed by waf, calls 'options' in sub-directories
    and detects those using pybind11
    """
    builder.configure(bld)
    builder.findpyext(bld, builder.wscripted('src'))
    for item in _ALL:
        bld.recurse(item)

def environment(cnf):
    u"prints the environment: use commandline 'python3 waf environment'"
    print(cnf.env)

def condaenv(_):
    u"prints the conda recipe"
    builder.condaenv('myprojectname')

def requirements(_):
    u"prints the project's requirements"
    builder.requirements()

# the following creates specific build functions for all
# sub-directories. Do 'python3 waf --help' to see this
builder.addbuild(_ALL)
~~~

