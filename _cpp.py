#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Default cpp for waf"
import sys
import re
from   pathlib          import Path
from typing             import Optional, List
from contextlib         import closing
from distutils.version  import LooseVersion
from waflib             import Utils
from waflib.Configure   import conf
from waflib.Context     import Context
from waflib.TaskGen     import after_method,feature
from ._utils            import (YES, runall, addmissing,
                                Make, copyargs, copyroot, loading)
from ._requirements     import REQ as requirements

IS_MAKE          = YES
CXX_OPTION_GROUP = 'C++ Options'
COMPILERS        = 'g++', 'clang++', 'msvc'
WARNINGS         = {Ellipsis: ['-Werror=implicit-function-declaration',
                               '-W', '-Wall', '-Wextra','-Wno-write-strings',
                               '-Wunused', '-Wuninitialized', '-fno-common',
                               '-Winit-self', '-Wpacked', '-Wpointer-arith',
                               '-Wmissing-format-attribute', '-Wmissing-noreturn',
                               '-Wswitch-enum', '-Wundef', '-Wunreachable-code',
                               '-Wmissing-include-dirs', '-Wparentheses',
                               '-Wsequence-point'],
                    'msvc':   ['/W3']}
FLAGS           = {'/std:c++14': '-std=c++14',
                   '/std:c++17': '-std=c++17',
                   '/std:c++20': '-std=c++20',
                   '/openmp':    '-fopenmp',
                   '/EHsc':      '',
                  }
COVERAGE        = {
    'g++': {"cxx": '-fprofile-arcs --coverage', 'links': "-lgcov --coverage"},
    'clang++': {"cxx": '-fprofile-instr-generate -fcoverage-mapping', 'links': "--coverage"},
}

def _ismsvc(cnf:Context):
    return cnf.env['COMPILER_CXX'] == 'msvc'

def _isrequired():
    return 'cpp' in requirements

class Flags(Make):
    u"deal with cxx/ld flags"
    DEFAULT_CXX = {'linux': '-std=c++17', 'msvc': '/std:c++14'}
    @classmethod
    def defaultcxx(cls) -> str:
        "return the default cxx"
        return cls.DEFAULT_CXX["msvc" if sys.platform.startswith('win') else 'linux']

    @classmethod
    def options(cls, opt):
        u"add options"
        if not _isrequired():
            return

        copt     = opt.add_option_group(CXX_OPTION_GROUP)
        cxxflags = cls.defaultcxx()+(' /EHsc' if sys.platform.startswith('win') else ' -g')

        copt.add_option('--cxxflags',
                        dest    = 'cxxflaglist',
                        default = cxxflags,
                        action  = 'store',
                        help    = f'define cxx flags (defaults are {cxxflags})')
        copt.add_option('--linkflags',
                        dest    = 'linkflaglist',
                        default = '',
                        action  = 'store',
                        help    = 'define link flags')
        copt.add_option('--lcov',
                        dest    = 'coverageflags',
                        default = False,
                        action  = 'store_true',
                        help    = 'add coverage flags')

    @staticmethod
    def convertFlags(cnf:Context, cxx, islinks = False):
        u"Converts the flabs to msvc equivalents"
        flags = {j: i for i, j in FLAGS.items()} if _ismsvc(cnf) else dict(FLAGS)
        delim =  ('-', '/')                      if _ismsvc(cnf) else ("/", "-")
        if islinks:
            flags[next(i for i in flags if i.endswith('openmp'))] = ''

        cxx   = ' '.join(flags.get(i, i) for i in cxx.split(' '))
        cxx   = cxx.replace(*delim)
        return cxx

    _DONE = False
    @classmethod
    def configure(cls, cnf:Context):
        u"setup configure"
        if not _isrequired() or cls._DONE:
            return
        cls._DONE = True

        warns = WARNINGS.get(cnf.env['COMPILER_CXX'], WARNINGS[...])
        cxx   = cnf.options.cxxflaglist + ' ' + ' '.join(warns)
        links = cnf.options.linkflaglist

        if cnf.options.coverageflags:
            name   = cnf.env['COMPILER_CXX']
            args   = COVERAGE.get(name, COVERAGE.get(name[:3], {}))
            cxx   += " "+args.get('cxx', '')
            links += " "+args.get('links', '')

        cxx   = cls.convertFlags(cnf, cxx)
        links = cls.convertFlags(cnf, links)

        cnf.check(features  = 'cxx cxxprogram',
                  cxxflags  = cxx,
                  linkflags = links,
                  mandatory = True)

        cnf.env.append_unique('CXXFLAGS',  Utils.to_list(cxx))
        cnf.env.append_unique('LINKFLAGS', Utils.to_list(links))
        cnf.env.append_unique('INCLUDES',  ['../'])
        cnf.env.append_unique('CXXFLAGS', warns)

class Boost(Make):
    u"deal with cxx/ld flags"
    _H_ONLY = 'accumulators', 'preprocessor'

    @staticmethod
    def getlibs():
        "find boost libs"
        names = set()
        curr  = LooseVersion('0.0')
        req   = requirements.version('cpp', allorigs = False)
        if req is None:
            return names, curr

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
        return 'boost' if len(cls.getlibs()[0]) else ''

    @classmethod
    def configure(cls, cnf:Context):
        u"setup configure"
        cnf.env.append_value('SYS_INCS', 'BOOST')
        libs, vers = cls.getlibs()
        if not len(libs):
            return

        if not cnf.options.boost_includes and not cnf.options.boost_libs:
            path = Path(cnf.env["PYTHON"][0]).parent
            if sys.platform.startswith("win32"):
                path /= "Library"

            for i in range(3):
                if (path/"include"/"boost").exists() and (path/"lib").exists():
                    cnf.options.boost_includes = str(path/"include")
                    cnf.options.boost_libs     = str(path/"lib")
                    break
                path = path.parent

        cnf.check_boost(lib = ' '.join(libs-set(cls._H_ONLY)), mandatory = True)
        if sys.platform.startswith("win32"):
            cnf.env['LIB_BOOST']= [i.replace("-sgd-", "-gd-") for i in cnf.env["LIB_BOOST"]]
        else:
            path = Path(cnf.env["LIBPATH_BOOST"][0])
            good = []
            for i in cnf.env["LIB_BOOST"]:
                if i.endswith('.so') and (path/f"lib{i}").exists():
                    good.append(i)
                elif (path/f"lib{i[:i.find('.so')+3]}").exists():
                    good.append(i[:i.find('.so')])
                else:
                    raise KeyError(f"missing $path/lib$i")
            cnf.env["LIB_BOOST"] = good
        if LooseVersion(cnf.env.BOOST_VERSION.replace('_', '.')) < vers:
            cnf.fatal('Boost version is too old: %s < %s'
                      % (str(vers), str(cnf.env.BOOST_VERSION)))

def toload(cnf:Context):
    u"returns all features needed by cpp"
    if not _isrequired():
        return ''

    load = 'compiler_cxx'
    if sys.platform == "win32":
        load += ' msvc msvs'

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
    if name.startswith('python_'):
        base = name[len('python_'):]
        cond = 'ver >= num('+str(version).replace('.',',')+')'
        cnf.check_python_module(base, condition = cond)

        if sys.platform.startswith('win'):
            root    = (Path(cnf.env.INCLUDES_PYEXT[0])/'..'/'Library').resolve()
            inc     = str((root/'include').resolve())
            lib     = str((root/'lib').resolve())
        else:
            inc      = cnf.env.INCLUDES_PYEXT[0]
            lib      = cnf.env.LIBPATH_PYEXT[0] if len(cnf.env.LIBPATH_PYEXT) else ""

        libflag  = "-L" if len(lib) else ""
        line = f' -I{inc} -I{Path(inc).parent} {libflag}{lib} -l{base}'
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
    if not (cnf.env.CC_NAME or cnf.env.CXX_NAME):
        return None

    curr = cnf.env['CC_VERSION']
    if _ismsvc(cnf):
        curr = cnf.env['MSVC_VERSION']
    if isinstance(curr, tuple):
        curr = '.'.join(str(i) for i in curr)

    return cnf.env['COMPILER_CXX']+"-"+str(curr)

if not sys.platform.startswith("win"):
    @feature('c','cxx','includes')
    @after_method('apply_incpaths')
    def apply_sysincpaths(self):
        "add system args to specific includes"
        sysitems: List[str] = []
        for i in self.env.SYS_INCS:
            itms = getattr(self.env, f'INCLUDES_{i}')
            if isinstance(itms, (list, tuple)):
                sysitems.extend(itms)
            else:
                sysitems.append(itms)

        cwd      = self.get_cwd()
        sysitems = [ str(self.bld.root.make_node(i).path_from(cwd)) for i in sysitems]

        self.env.INCPATHS= [
            str(x)
            for x in self.env.INCPATHS
        ]

        self.env.INCPATHS= [
            ('SYSTEM' if x in sysitems else '') + x
            for x in self.env.INCPATHS
        ]

    from waflib.Task import Task
    def exec_command(self,cmd, __old__ = Task.exec_command, **kw):
        "execute cmd"
        if isinstance(cmd, list):
            old = list(cmd)
            cmd.clear()
            cmd.extend(i.replace('-ISYSTEM', '-isystem') for i in old)
        return __old__(self, cmd, **kw)
    Task.exec_command = exec_command
addmissing(locals())
