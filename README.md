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
*cppx17* is used automatically.

### NodeJS

Files with the '.ts' (typescript) or '.coffee' are automatically copied to the build directory.
This can be done without adding 'nodejs' to requirements.

#### Coffeescript
Compilation and linting is performed automatically provided the extension used
is '.coffee' and the wscrip is configured so: see Coffeescript support lower down.

#### Typescript
No linting or compiling is provided: it is not mandatory to add a requirement.


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

# Make a suggestion to the user:
suggest(sphynx = 2.0, rtime = False)
~~~

### When using a conda environment

Using a project-specific conda environment is a swell idea. This can be done
automatically as follows:
~~~
python waf setup -e MYCONDAENVNAME     # create the env
python waf configure -e MYCONDAENVNAME # configure *using* the new env
python waf build                       # build *using* the new env
python waf test                        # test *using* the new env
~~~

One can use MYCONDAENVNAME="branch" to have the current branch name automatically used.

It can be more convienient to create a new env from an old one and then only change specific packages.
~~~
conda create -n NEWENV --clone OLDENV
conda install bokeh=5.0 -c conda-forge
...
~~~

### Creating a conda environment

# The wscript file

## Building a single dynamic library or python modules:

Simply add:
~~~
make()
~~~

The *wafbuilder* will set things up automatically.

This is not even required should there be a line as follows in the main *wscript*:
~~~
import wafbuilder as builder
builder.defaultwscript("src") # all children directories in 'src' have a default wscript
~~~

## Adding Coffeescript support

The file then looks like:
~~~
require('nodejs', nodejs = 10.0, coffeescript = 2.0)
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
from wafbuilder import require, suggest

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

# add default options/configure/build/test
# and add support for conda envs & app packaging (apppackager = True)
from wafbuilder.modules import globalmake
globalmake(apppackager = True)
~~~
