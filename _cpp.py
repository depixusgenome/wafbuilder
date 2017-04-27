#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Default cpp for waf"
import sys
import re
from   pathlib          import Path
from typing             import Optional
from contextlib         import closing
from distutils.version  import LooseVersion
from waflib             import Utils
from waflib.Configure   import conf
from waflib.Context     import Context
from ._utils            import (YES, runall, addmissing,
                                Make, copyargs, copyroot, loading)
from ._requirements     import REQ as requirements

IS_MAKE          = YES
CXX_OPTION_GROUP = 'C++ Options'
COMPILERS        = 'g++', 'clang++', 'msvc'

def _ismsvc(cnf:Context):
    return cnf.env['COMPILER_CXX'] == 'msvc'

def _isrequired():
    return 'cpp' in requirements

class Flags(Make):
    u"deal with cxx/ld flags"
    @staticmethod
    def options(opt):
        u"add options"
        if not _isrequired():
            return

        copt = opt.add_option_group(CXX_OPTION_GROUP)
        if sys.platform.startswith('win'):
            cxxflags = '/std:c++14 /EHsc'
        else:
            cxxflags = '-std=c++14 -g'

        copt.add_option('--cxxflags',
                        dest    = 'cxxflaglist',
                        default = cxxflags,
                        action  = 'store',
                        help    = 'define cxx flags')
        copt.add_option('--linkflags',
                        dest    = 'linkflaglist',
                        default = '',
                        action  = 'store',
                        help    = 'define link flags')

    @staticmethod
    def convertFlags(cnf:Context, cxx, islinks = False):
        u"Converts the flabs to msvc equivalents"
        if not _ismsvc(cnf):
            return cxx

        flags = {'-std=c++14': '/std:c++14',
                 '-fopenmp':   '' if islinks else '/openmp',
                 '-g':         '',
                }
        cxx   = ' '.join(flags.get(i, i) for i in cxx.split(' '))
        cxx   = cxx.replace('-', '/')
        return cxx

    _DONE = False
    @classmethod
    def configure(cls, cnf:Context):
        u"setup configure"
        if not _isrequired() or cls._DONE:
            return
        cls._DONE = True

        warnings = [
            '-Werror=implicit-function-declaration',
            '-W', '-Wall', '-Wextra','-Wno-write-strings', '-Wunused',
            '-Wuninitialized',
            '-fno-common', '-Winit-self', '-Wpacked',
            '-Wpointer-arith', '-Wmissing-format-attribute',
            '-Wmissing-noreturn',
            '-Wswitch-enum', '-Wundef',
            '-Wunreachable-code',
            '-Wmissing-include-dirs',
            '-Wparentheses',
            '-Wsequence-point',
            ]
        if _ismsvc(cnf):
            warnings = ['/W3']

        cxx   = cnf.options.cxxflaglist + ' ' + ' '.join(warnings)

        links = cnf.options.linkflaglist

        cxx   = cls.convertFlags(cnf, cxx)
        links = cls.convertFlags(cnf, links)

        cnf.check(features  = 'cxx cxxprogram',
                  cxxflags  = cxx,
                  linkflags = links,
                  mandatory = True)

        cnf.env.append_unique('CXXFLAGS',  Utils.to_list(cxx))
        cnf.env.append_unique('LINKFLAGS', Utils.to_list(links))
        cnf.env.append_unique('INCLUDES',  ['../'])
        cnf.env.append_unique('CXXFLAGS', warnings)

class Boost(Make):
    u"deal with cxx/ld flags"
    _H_ONLY = 'accumulators',

    @staticmethod
    def _getlibs():
        names = set()
        curr  = LooseVersion('0.0')
        req   = requirements.version('cpp', allorigs = False)
        if req is None:
            return
        for name, origs in req.items():
            if not name.startswith('boost_'):
                continue

            names.add(name.split('_')[-1])
            for vers, _ in origs.values():
                if vers is not None and vers > curr:
                    curr = vers
        return names, curr

    @classmethod
    def toload(cls, _:Context):
        u"returns boost feature if required"
        return 'boost' if len(cls._getlibs()[0]) else ''

    @classmethod
    def configure(cls, cnf:Context):
        u"setup configure"
        libs, vers = cls._getlibs()
        if len(libs):
            cnf.check_boost(lib = ' '.join(libs-set(cls._H_ONLY)), mandatory = True)
            if LooseVersion(cnf.env.BOOST_VERSION.replace('_', '.')) < vers:
                cnf.fatal('Boost version is too old: %s < %s'
                          % (str(vers), str(cnf.env.BOOST_VERSION)))

def toload(cnf:Context):
    u"returns all features needed by cpp"
    if not _isrequired():
        return ''

    load = 'compiler_cxx'
    if sys.platform == "win32":
        load += ' msvc'

    if ('cpp', 'python_.*') in requirements:
        load += ' python'

    return loading(cnf, ' '.join((load, Boost.toload(cnf))))

@runall
def options(opt:Context):
    u"add options"
    if _isrequired():
        opt.add_option_group(CXX_OPTION_GROUP)

@requirements.addcheck(lang = 'cxx', name = COMPILERS)
def check_cpp_compiler(cnf:Context, name:str, version:Optional[str]):
    u"checks the compiler version"
    if cnf.env['COMPILER_CXX'] != name:
        return

    curr = cnf.env['CC_VERSION']
    if _ismsvc(cnf):
        curr = cnf.env['MSVC_VERSION']
    if isinstance(curr, float):
        curr = str(curr)
    elif isinstance(curr, tuple):
        curr = '.'.join(curr)

    if LooseVersion(curr) < version:
        cnf.fatal(cnf.env['COMPILER_CXX']
                  +' version '+curr
                  +' should be greater than '+version)

@requirements.addcheck
def check_cpp_default(cnf:Context, name:str, version:Optional[str]):
    u"Adds a requirement checker"
    if name.startswith('boost'):
        return
    elif name.startswith('python_'):
        base = name[len('python_'):]
        cond = 'ver >= num('+str(version).replace('.',',')+')'
        cnf.check_python_module(base, condition = cond)

        if sys.platform.startswith('win'):
            root = (Path(cnf.env.INCLUDES_PYEXT[0])/'..'/'Library').resolve()
            inc  = str((root/'include').resolve())
            lib  = str((root/'lib').resolve())
        else:
            inc  = cnf.env.INCLUDES_PYEXT[0]
            lib  = cnf.env.LIBPATH_PYEXT[0]
        line = ' -I'   + inc + ' -L' + lib + ' -l' + base
        if not sys.platform.startswith('win'):
            line += ' -lm'
        libs = tuple(pre+base+suf for pre in ('', 'lib') for suf in ('.so', '.dll', '.lib'))
        if not any((Path(lib) / name).exists() for name in libs):
            line = line.replace('-l'+base, '')

        cnf.parse_flags(line, uselib_store = base)
    else:
        cnf.check_cfg(package         = name,
                      uselib_store    = name,
                      args            = '--cflags --libs',
                      atleast_version = version)

def hasmain(csrc):
    u"detects whether a main function is declared"
    pattern = re.compile(r'\s*int\s*main\s*(\s*int\s*\w+\s*,\s*(const\s*)?char\s')
    for item in csrc:
        with closing(open(item.abspath(), 'r')) as stream:
            if any(pattern.match(line) is not None for line in stream):
                return item
    return None

@conf
def build_cpp(bld:Context, name:str, version:str, **kwargs):
    u"builds a cpp extension"
    csrc = bld.path.ant_glob('**/*.cpp', exclude = kwargs.get('python_cpp', []))
    if len(csrc) == 0:
        return

    prog = hasmain(csrc)
    csrc = [i for i in csrc if csrc is not prog]

    args = copyargs(kwargs)
    args.setdefault('target', copyroot(bld,None).make_node(name))

    def _template(post):
        res = bld.srcnode.find_resource(__package__+'/_program.template')
        return bld(features = 'subst',
                   source   = res,
                   target   = name+"_%sheader.cpp" % post,
                   name     = str(bld.path)+":%sheader" % post,
                   nsname   = name+'_'+post,
                   version  = version).target

    if len(csrc):
        csrc.append(_template('lib'))
        args['source'] = csrc
        args['name']   = name+"_lib"
        bld.shlib(**args)

    if prog is not None:
        args['source'] = [prog, _template('program')]
        args['name']   = name+"_prog"
        if len(csrc):
            args.setdefault('use', []).append(name+'_lib')
        bld.program(**args)

@conf
def cpp_compiler_name(cnf:Context):
    u"Returns the compiler version used"
    curr = cnf.env['CC_VERSION']
    if _ismsvc(cnf):
        curr = cnf.env['MSVC_VERSION']
    if isinstance(curr, tuple):
        curr = '.'.join(str(i) for i in curr)

    return cnf.env['COMPILER_CXX']+"-"+str(curr)

addmissing(locals())
