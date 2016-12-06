#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Default cpp for waf"
from ._utils import YES, runall, addmissing, Make, requirements
from waflib  import Utils

IS_MAKE = YES
CXX_OPTION_GROUP = 'C++ Options'

class Flags(Make):
    u"deal with cxx/ld flags"
    @staticmethod
    def options(opt):
        u"add options"
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

    @classmethod
    def _requirements(cls, cnf):
        info = requirements("cxx")
        curr = cnf.env['CC_VERSION']
        if cls._ismsvc(cnf):
            curr = cnf.env['MSVC_VERSION']
            if isinstance(curr, float):
                curr = str(curr).split('.')

        if cnf.env['COMPILER_CXX'] not in info:
            cnf.fatal(cnf.env['COMPILER_CXX'] +' min version should be set in the REQUIRE file')

        minv = info[cnf.env['COMPILER_CXX']]
        if tuple(int(val) for val in curr) < tuple(int(val) for val in minv):
            cnf.fatal(cnf.env['COMPILER_CXX']
                      +' version '+'.'.join(curr)
                      +' should be greater than '+'.'.join(minv))

    @staticmethod
    def _ismsvc(cnf):
        return cnf.env['COMPILER_CXX'] == 'msvc'

    @classmethod
    def convertFlags(cls, cnf, cxx, islinks = False):
        u"Converts the flabs to msvc equivalents"
        if not cls._ismsvc(cnf):
            return cxx

        flags = {'-std=c++14': '/std:c++14',
                 '-fopenmp':   '' if islinks else '/openmp',
                 '-g':         '',
                 }
        cxx   = ' '.join(flags.get(i, i) for i in cxx.split(' '))
        cxx   = cxx.replace('-', '/')
        return cxx

    @classmethod
    def configure(cls, cnf):
        u"setup configure"
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
        if cls._ismsvc(cnf):
            warnings = ['-Wall']

        cxx   = cnf.options.cxxflaglist + ' ' + ' '.join(warnings)

        links = cnf.options.linkflaglist
        if cnf.options.noopenmp:
            cxx   = cxx.replace('-fopenmp', '')
            links = links .replace('-fopenmp', '')

        cls._requirements(cnf)
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
    return 'compiler_cxx'

@runall
def options(opt):
    u"add options"
    opt.add_option_group(CXX_OPTION_GROUP)

addmissing(locals())
