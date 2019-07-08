#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Default cpp for waf"
import sys
import re
import textwrap
from   pathlib          import Path
from typing             import Optional, List, Tuple, Dict
from distutils.version  import LooseVersion
from waflib             import Utils,Errors
from waflib.Configure   import conf
from waflib.Context     import Context
from waflib.TaskGen     import after_method,feature
from ._utils            import YES, runall, addmissing, Make, loading
from ._requirements     import REQ as requirements
from .git               import (
    lasthash       as _gitlasthash,
    isdirty        as _gitisdirty,
    lasttimestamp  as _gitlasttimestamp
)

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

DEFAULT_CXX = {
    **dict.fromkeys(('g++', 'clang++', 'linux'), '-std=c++17 -g'),
    **dict.fromkeys(('msvc',),                   '/std:c++17 /EHsc')
}

OPTIONS = {
    '+coverage': {
        'g++':     {
            'cxx':   '-fprofile-arcs --coverage',
            'links': '-lgcov --coverage'
        },
        'clang++': {
            'cxx':   '-fprofile-instr-generate -fcoverage-mapping',
            'links': '--coverage'
        },
    },
    '+sanitize': {
        i: {
            'cxx':   '-fsanitize=address -fno-omit-frame-pointer -O0',
            'links': '-fsanitize=address'
        } for i in ('g++', 'clang++')
    }
}

def _ismsvc(cnf:Context):
    return cnf.env['COMPILER_CXX'] == 'msvc'

def _isrequired():
    return 'cpp' in requirements

class Flags(Make):
    "deal with cxx/ld flags"
    @classmethod
    def defaultcxx(cls) -> str:
        "return the default cxx"
        return DEFAULT_CXX["msvc" if sys.platform.startswith('win') else 'linux']


    @classmethod
    def options(cls, opt):
        u"add options"
        if not _isrequired():
            return

        copt     = opt.add_option_group(CXX_OPTION_GROUP)
        cxxflags = cls.defaultcxx()

        copt.add_option(
            '--cxxflags',
            dest    = 'cxxflaglist',
            default = cxxflags,
            action  = 'store',
            help    = textwrap.dedent(f'''
                define cxx flags (defaults are {cxxflags}). The following is understood:
                    - a '+' as first character will be replaced by '{cxxflags}.
                    - '+coverage' will be replaced by '{OPTIONS['+coverage']['g++']['cxx']}'.
                    - '+sanitize' will be replaced by '{OPTIONS['+sanitize']['g++']['cxx']}'.
            ''')
        )

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
        copt.add_option('--sanitize',
                        dest    = 'sanitizeflags',
                        default = False,
                        action  = 'store_true',
                        help    = 'add sanitizing flags')

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

        name  = cnf.env['COMPILER_CXX']
        cxx   = cnf.options.cxxflaglist
        links = cnf.options.linkflaglist

        # add options
        for i, j in OPTIONS.items():
            if i not in cxx and getattr(cnf.options, i[1:]+'flags'):
                cxx += ' ' + i
            if i in cxx and name in j:
                cxx   = cxx.replace(i, j[name].get('cxx', ''))
                links = links.strip()+" "+j[name].get('links', '')

        # add default flags
        if cxx[0] == "+":
            cxx = cls.defaultcxx().strip()+" "+cxx[1:]

        # add warnings
        cxx  +=  ' ' + ' '.join(WARNINGS.get(name, WARNINGS[...]))

        cxx   = cls.convertFlags(cnf, cxx)
        links = cls.convertFlags(cnf, links)

        cnf.check(features  = 'cxx cxxprogram',
                  cxxflags  = cxx,
                  linkflags = links,
                  mandatory = True)

        cnf.env.append_unique('CXXFLAGS',  Utils.to_list(cxx))
        cnf.env.append_unique('LINKFLAGS', Utils.to_list(links))
        cnf.env.append_unique('INCLUDES',  ['../'])

class Boost(Make):
    u"deal with cxx/ld flags"
    _H_ONLY = 'accumulators', 'preprocessor', 'beast'

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
            cls.__getboostfromconda(cnf)

        cnf.check_boost(lib = ' '.join(libs-set(cls._H_ONLY)), mandatory = True)
        if 'LIB_BOOST' not in cnf.env:
            cnf.env['LIB_BOOST']= []
        elif sys.platform.startswith("win32"):
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

    @staticmethod
    def __getboostfromconda(cnf:Context):
        rem = 'PYTHON' not in cnf.env
        if rem:
            cnf.find_program("python", var="PYTHON", mandatory=False)
        if 'PYTHON' in cnf.env:
            path = Path(cnf.env["PYTHON"][0]).parent

            if sys.platform.startswith("win32"):
                path /= "Library"

            for _ in range(3):
                if (path/"include"/"boost").exists() and (path/"lib").exists():
                    cnf.options.boost_includes = str(path/"include")
                    cnf.options.boost_libs     = str(path/"lib")
                    break
                path = path.parent
        if rem:
            del cnf.env['PYTHON']

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

def get_python_paths(cnf:Context, name:str, version: Optional[str]) -> Dict[str, Path]:
    "get the python path"
    rem = not getattr(cnf.env, 'PYTHON')
    if rem:
        cnf.find_program("python", var="PYTHON", mandatory=False)

    if not getattr(cnf.env, 'PYTHON'):
        check_cpp_default(cnf, name, version)

    root = Path(cnf.env["PYTHON"][0]).parent
    if rem:
        del cnf.env['PYTHON']

    path = root/'Library' if sys.platform.startswith('win') else root.parent
    return dict(
        root = root.resolve(),
        inc  = (path/'include').resolve(),
        lib  = (path/'lib').resolve(),
        bin  = (path/'bin').resolve()
    )

@requirements.addcheck
def check_cpp_gtest(cnf:Context, name:str, version:Optional[str]):
    "check for gtest"
    path = get_python_paths(cnf, name, version)['lib']
    vers = libmain = lib = inc = None
    cnf.start_msg(f"Checking for conda module {name} (>= {version})")
    for i in range(3):
        inc     = path/"include"/"gtest"
        libmain = path/"lib"/f"lib{name}_main.a"
        lib     = path/"lib"/f"lib{name}.a"
        if inc.exists() and lib.exists():
            break
        path = path.parent
    else:
        cnf.end_msg(False)
        cnf.fatal('Could not find the conda module ' +name)
        return

    setattr(cnf.env, f"INCLUDES_{name}",  [str(inc.parent)])
    setattr(cnf.env, f"STLIBPATH_{name}", [str(lib.parent)])
    setattr(cnf.env, f"STLIB_{name}",     [i.stem.replace('lib', '') for i in (lib, libmain)])
    setattr(cnf.env, f"LIB_{name}",       ['pthread'])
    if version is None:
        cnf.end_msg(True)
        return

    try:
        ret = cnf.cmd_and_log(["conda", "list", name])
    except Errors.WafError:
        pass
    else:
        out = ret.strip().split('\n')
        if len(out) == 4:
            vers  = next((i for i in out[-1].split(" ")[1:] if i != ""), None)
            cnf.end_msg(vers)
            return

    cnf.fatal('The %s version does not satisfy the requirements'%name)
    cnf.end_msg(False)

PYTHON_MODULE_LIBS = {
    'ffmpeg': ["avformat", "avcodec", "avutil"]
}

def _check_cpp_python(cnf:Context, name:str, version:Optional[str]):
    base     = name[len('python_'):]
    cond     = 'ver >= num('+str(version).replace('.',',')+')'
    cnf.check_python_module(base, condition = cond)
    paths    = get_python_paths(cnf, name, version)
    lib, inc = paths['lib'], paths['inc']
    line     = f' -I{inc} -I{Path(inc).parent} -L{lib}'
    iswin    = sys.platform.startswith('win')
    if not iswin:
        line += ' -lm'

    bases    = set(PYTHON_MODULE_LIBS.get(base, (base,)))
    fullname = "--dummy--"
    for basename in set(bases):
        for fullname in (
                pre+basename+suf
                for pre in ('', 'lib')
                for suf in ('.so', '.dll', '.lib')
        ):
            if (Path(lib) / fullname).exists():
                line  += f' -l{basename}'
                bases -=  {basename}
                break

    for basename in bases:
        for lib in (pre+basename+'.a' for pre in ('', 'lib')):
            if (Path(lib) / fullname).exists():
                if '-Wl,-Bstatic' not in line:
                    line += f' -Wl,-Bstatic -L{lib}'
                line += f' l{basename}'
                break

    cnf.parse_flags(line, uselib_store = base)
    for suf in ('', '.exe', '.bat', '.sh'):
        test = (paths['bin']/base).with_suffix(suf)
        if test.exists():
            setattr(cnf.env, f"BIN_{base}",  [str(test)])
            cnf.env.append_value(f'DEFINES_{base}', f'BIN_{base}="{test}"')

@requirements.addcheck
def check_cpp_default(cnf:Context, name:str, version:Optional[str]):
    u"Adds a requirement checker"
    if name.startswith('boost'):
        return

    if name.startswith('python_'):
        _check_cpp_python(cnf, name, version)
    else:
        cnf.check_cfg(package         = name,
                      uselib_store    = name,
                      args            = '--cflags --libs',
                      atleast_version = version)

_GTEST = re.compile(r'^\s*TEST\(')
_MAIN  = re.compile(r'^\s*int\s+main\s*\(\s*int[\s,].*')
def splitmains(csrc, patt) -> Tuple[List[Path], List[Path]]:
    "detects whether a main function is declared"
    itms    = [], []
    for item in csrc:
        with open(item.abspath(), 'r', encoding = 'utf-8') as stream:
            itms[any(patt.match(line) for line in stream)].append(item)
    return itms

@conf
def build_cpp(bld:Context, name:str, version:str, ignore = None, **kwargs):
    u"builds a cpp extension"
    rem  = [str(bld.bldnode)]
    rem += (
        [ignore]        if isinstance(ignore, str) else
        list(ignore)    if ignore                  else
        []
    )
    csrc = [
        i
        for i in bld.path.ant_glob('**/*.cpp', exclude = kwargs.get('python_cpp', []))
        if not any(str(i).startswith(j) for j in rem)
    ]
    if len(csrc) == 0:
        return

    csrc, progs  = splitmains(csrc, _MAIN)
    csrc, gtests = splitmains(csrc, _GTEST)

    kwargs["use"] = [*kwargs.get("use", []), *build_stlib(bld, name, version, csrc, **kwargs)]
    build_prog(bld, name, version, progs, csrc, **kwargs)
    build_gtests(bld, name, gtests, **kwargs)

def build_stlib(bld, name, version, csrc, **args):
    "build a lib"
    args.setdefault('target', name)
    if len(csrc):
        csrc.extend(build_versioncpp(bld, name, version, "lib"))
        args['source'] = csrc
        args['name']   = name+"_lib"
        return [bld.stlib(**args).name]
    return []

def build_versioncpp(bld, name, version, post):
    "buld a .cpp file containing version info"
    return [bld(
        features = 'subst',
        source   = bld.srcnode.find_resource(__package__+'/_program.template'),
        target   = name+"_%sheader.cpp" % post,
        name     = str(bld.path)+":%sheader" % post,
        nsname   = name+'_'+post,
        version  = version,
        lasthash = _gitlasthash(name),
        isdirty  = _gitisdirty(name),
        timestamp= _gitlasttimestamp(name),
        cpp_compiler_name = bld.cpp_compiler_name()
    ).target]


def build_prog(bld, name, version, progs, csrc, **args):
    "build programs"
    sources = (
        build_versioncpp(bld, name, version, 'program')
        if len(progs) and not len(csrc) else
        []
    )
    specs   = {
        prog: args.pop(Path(str(prog)).stem, {})
        for prog in progs[::-1]
    }
    for prog in progs[::-1]:
        progname = Path(str(prog)).stem
        bld.program(**dict(
            args,
            source = [prog]+sources,
            target = progname,
            name   = name + ': ' + progname,
            use    = (
                args.get('use', [])
                # add libs specific to the program
                + specs[prog].get('use', [])
            ),
            # add args specific to the program
            **{i: j for i, j in specs[prog].items() if i != 'use'}
        ))

def build_gtests(bld, name, sources, **kwa):
    "build gtests"
    if sources:
        bld.program(**dict(
            kwa,
            source = sources,
            target = f"{name}_test_all",
            name   = name + ': test_all',
            use    = kwa.get("use", [])+["gtest"]
        ))

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
    if isinstance(cmd, list) and any('ISYSTEM' in i for i in cmd):
        old = list(cmd)
        cmd.clear()
        if sys.platform.startswith('win'):
            cmd.append(old[0])
            cmd.append('/experimental:external')
            cmd.append('/external:W0')
            cmd.extend(i.replace('/ISYSTEM', '/external:I') for i in old[1:])
        else:
            cmd.extend(i.replace('-ISYSTEM', '-isystem') for i in old)
    return __old__(self, cmd, **kw)
Task.exec_command = exec_command
addmissing(locals())
