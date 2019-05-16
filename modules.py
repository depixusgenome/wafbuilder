#!/usr/bin/env python3
# encoding: utf-8
"The list of modules"
from   pathlib          import Path
from   contextlib       import contextmanager

from   waflib.Build     import BuildContext
from   waflib.Configure import ConfigurationContext

import wafbuilder

def basecontext(bld):
    "returns the base context"
    return BuildContext if (Path(bld)/'c4che').exists() else ConfigurationContext

class Modules:
    "sets-up the modules"
    def __init__(self, singles = ("tests", "scripts"), src = "src", binit = True):
        if binit:
            wafbuilder.defaultwscript(src, "make(locals())")
        self._all  = () if singles is None else tuple(i for i in singles if Path(i).exists())
        if src is not None:
            self._all += tuple(wafbuilder.wscripted(src))
        self._src  = src

    @staticmethod
    def run_condaenvname(cnf):
        "prints requirements"
        from wafbuilder.shellvars import condaenvname
        condaenvname(cnf)

    def run_requirements(self, cnf):
        "prints requirements"
        from wafbuilder import requirements as _REQ
        self(cnf)
        _REQ.tostream()

    def run_options(self, opt):
        "create options"
        # pylint: disable=no-member
        wafbuilder.load(opt)
        with self.options(opt):
            wafbuilder.options(opt)

    def run_configure(self, cnf):
        "configure wafbuilder"
        with self.configure(cnf):
            wafbuilder.configure(cnf)

    def run_tests(self, bld, root = 'tests'):
        "runs pytests"
        mods  = ('/'+i.split('/')[-1] for i in self(bld))
        names = (path for path in bld.path.ant_glob((root+'/*test.py', root+'/*/*test.py')))
        names = (str(name) for name in names if any(i in str(name) for i in mods))
        wafbuilder.runtest(bld, *(name[name.rfind('tests'):] for name in names))

    def run_build(self, bld, mods = None):
        "compile sources"
        if mods is None:
            mods = self(bld)
        bld.build_python_version_file()
        wafbuilder.build(bld) # pylint: disable=no-member
        wafbuilder.findpyext(bld, set(mod for mod in mods if mod != 'tests'))
        bld.recurse(mods, 'build')

    def build_static(self, bld):
        "transfer static sources"
        files = bld.path.ant_glob([i+"/**/static/*."+j
                                   for j in ("css", "js", "map", "svg", "eot",
                                             "ttf", "woff")
                                   for i in self._src])
        wafbuilder.copyfiles(bld, 'static', files)

    def check_linting(self, bld): # pylint: disable=too-many-locals
        "display linting info"
        stats: dict = {'count': 0}
        patt        = "pylint: disable="
        for src in self._src:
            for name in bld.path.ant_glob(src+"/**/*.py"):
                if "scripting" in str(name):
                    continue

                mdl = str(name)[len(str(bld.path)+"/"+src+"/"):]
                mdl = mdl[:mdl.find('/')]
                with open(str(name), 'r') as stream:
                    for line in stream:
                        if patt not in line:
                            continue
                        stats['count'] += 1
                        tpe = line[line.find(patt)+len(patt):].strip()
                        if " " in tpe:
                            tpe = tpe[:tpe.find(" ")]
                        for i in tpe.split(","):
                            info = stats.setdefault(i, {'count': 0})
                            info ['count'] += 1
                            info.setdefault(mdl, 0)
                            info[mdl] += 1

        print(f"""
            Totals
            =====
            
            count: {stats.pop('count')}
              """)
        for i, j in sorted(stats.items(), key = lambda x: x[1]['count'])[::-1]:
            cnt  = j.pop("count")
            itms = sorted(j.items(), key = lambda k: k[1])[::-1][::5]
            print(f"{str(i)+':':<35}{cnt:>5}\t\t{itms}")

    @classmethod
    def make(cls, locs, simple = False):
        "simple config"
        cls().addbuild(locs, simple = simple)

    def simple(self, cachepath = 'build/'):
        "simple config"
        class _CondaEnvName(BuildContext):
            fun = cmd = 'condaenvname'
        class _Requirements(basecontext(cachepath)):
            fun = cmd = 'requirements'
        class _Test(BuildContext):
            fun = cmd = 'test'

        return dict(_CondaEnvName = _CondaEnvName,
                    _Requirements = _Requirements,
                    _Test         = _Test,
                    requirements  = self.run_requirements,
                    condaenvname  = self.run_condaenvname,
                    options       = self.run_options,
                    configure     = self.run_configure,
                    build         = self.run_build,
                    test          = self.run_tests)

    def addbuild(self, locs, simple = False):
        "adds build methods"
        wafbuilder.addbuild(self._all, locs)
        if simple:
            locs.update(self.simple())

    def __call__(self, bld):
        "returns the required modules"
        defaults  = getattr(bld.env, 'modules', tuple())
        if bld.options.dyn is True or defaults is None or len(defaults) == 0:
            names = {val.split('/')[-1]: val for val in self._all}

            bld.options.all_modules = names
            bld.env.modules         = tuple()
            if len(bld.options.app):
                vals = tuple(names[i] for i in bld.options.app.split(','))
                bld.recurse(vals, 'defaultmodules', mandatory = False)

            defaults = bld.env.modules
            if len(defaults) == 0:
                defaults = self._all
            else:
                print("Selected modules:", defaults)

        requested = bld.options.modules
        if requested is None or len(requested) == 0:
            mods = defaults
        else:
            mods = tuple(names[req] for req in requested.split(',') if req in names)

        wafbuilder.requirements.reload(('',)+tuple(mods))
        return mods

    @contextmanager
    def options(self, opt):
        "adds options for selecting modules"
        opt.recurse(self._all)
        yield
        opt.add_option('--mod',
                       dest    = 'modules',
                       default = '',
                       action  = 'store',
                       help    = u"modules to build")
        opt.add_option('--dyn',
                       dest    = 'dyn',
                       action  = 'store_true',
                       default = None,
                       help    = (u"consider only modules which were here"
                                  +u" when configure was last launched"))
        opt.add_option('--app',
                       dest    = 'app',
                       action  = 'store',
                       default = '',
                       help    = (u"consider only modules which are "
                                  +u" necessary for provided applications"))

    @contextmanager
    def configure(self, cnf):
        "sets-up modules"
        cnf.env.app = cnf.options.app.split(',') if len(cnf.options.app) else []

        if cnf.options.dyn is None and len(cnf.options.modules) == 0:
            cnf.env.modules = tuple()
            mods            = self(cnf)
        else:
            cnf.env.modules = self(cnf)
            mods            = cnf.env.modules

        yield

        cnf.recurse(mods)
