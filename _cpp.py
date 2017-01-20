#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Default cpp for waf"
import sys
from typing             import Optional
from distutils.version  import LooseVersion
from waflib             import Utils
from waflib.Context     import Context
from ._utils            import YES, runall, addmissing, Make
from ._requirements     import requirementcheck, isrequired

IS_MAKE          = YES
CXX_OPTION_GROUP = 'C++ Options'
COMPILERS        = 'g++', 'clang++', 'msvc'

def _ismsvc(cnf:Context):
    return cnf.env['COMPILER_CXX'] == 'msvc'

def _isrequired():
    return isrequired('cpp')

class Flags(Make):
    u"deal with cxx/ld flags"
    @staticmethod
    def options(opt):
        u"add options"
        if not _isrequired():
            return

        copt = opt.add_option_group(CXX_OPTION_GROUP)
        copt.add_option('--cxxflags',
                        dest    = 'cxxflaglist',
                        default = '-std=c++14 -fopenmp -g',
                        action  = 'store',
                        help    = 'define cxx flags')
        copt.add_option('--linkflags',
                        dest    = 'linkflaglist',
                        default = '-fopenmp',
                        action  = 'store',
                        help    = 'define link flags')
        copt.add_option('--no-openmp',
                        dest     = 'noopenmp',
                        default  = False,
                        action   = 'store_true',
                        help     = 'disable OpenMP')

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
            warnings = ['-Wall']

        cxx   = cnf.options.cxxflaglist + ' ' + ' '.join(warnings)

        links = cnf.options.linkflaglist
        if cnf.options.noopenmp:
            cxx   = cxx.replace('-fopenmp', '')
            links = links .replace('-fopenmp', '')

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

def loads():
    u"returns all features needed by cpp"
    if not _isrequired():
        return ''
    if sys.platform == "win32":
        return 'compiler_cxx msvc'
    return 'compiler_cxx'

@runall
def options(opt:Context):
    u"add options"
    if _isrequired():
        opt.add_option_group(CXX_OPTION_GROUP)

@requirementcheck
def check_cpp_default(cnf:Context, name:str, version:Optional[str]):
    u"Adds a requirement checker"
    if name in COMPILERS:
        if cnf.env['COMPILER_CXX'] != name:
            return

        curr = cnf.env['CC_VERSION']
        if _ismsvc(cnf):
            curr = cnf.env['MSVC_VERSION']
        if isinstance(curr, float):
            curr = str(curr)
        elif isinstance(curr, tuple):
            curr = '.'.join(curr)

        if LooseVersion(curr) < LooseVersion(version):
            cnf.fatal(cnf.env['COMPILER_CXX']
                      +' version '+curr
                      +' should be greater than '+version)
    else:
        cnf.check_cfg(package         = name,
                      uselib_store    = name,
                      args            = '--cflags --libs',
                      atleast_version = version)
addmissing(locals())
