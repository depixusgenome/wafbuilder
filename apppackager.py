#!/usr/bin/env python3
# encoding: utf-8
"Everything related to conda"
import sys
import os
from pathlib    import Path
from itertools  import chain
from zipfile    import ZipFile
from shutil     import rmtree, copy2, move
from typing     import List
import py_compile

from waflib.Build   import BuildContext

from .git           import version
from .modules       import basecontext
from ._python       import condaenv as _condaenv, condasetup as _condasetup
from ._utils        import getlocals

class AppPackager(BuildContext):
    "Context for packaging an app"
    doall         = True
    excluded      = 'tests', 'scripting'
    pypath        = "OUTPUT_PY"
    outpath       = "OUTPUT"
    libname       = "pylib"
    resourcepaths: List[str] = []
    staticdir     = "static"
    appdir        = "app"
    codedir       = "code"
    docdir        = "doc"
    changelogpath = "CHANGELOG.md"

    def __clean(self):
        self.options.APP_PATH = self.bldnode.make_node(self.pypath)
        if self.options.APP_PATH.exists():
            self.options.APP_PATH.delete()

        self.options.OUT_PATH = self.bldnode.make_node(self.outpath)
        if self.options.OUT_PATH.exists():
            self.options.OUT_PATH.delete()
        self.options.OUT_PATH.mkdir()

    @staticmethod
    def __compile(path, inp, outp):
        if str(inp).endswith(".pyc"):
            return inp
        try:
            with open(str(inp), encoding = 'utf-8') as stream:
                if any('from_py_func' in i for i in stream):
                    return inp
        except UnicodeDecodeError:
            pass

        cur = outp/inp.relative_to(path).with_suffix('.pyc')
        out = str(cur)
        opt = 0 if 'reporting' in out else 2
        py_compile.compile(str(inp), out, optimize = opt)
        return cur

    def __zip_files(self, path, out, zips):
        with ZipFile(str(out/(self.libname+".pyz")), "w") as zfile:
            for pyc in path.glob("*.py"):
                pyc = self.__compile(path, pyc, path)
                zfile.write(str(pyc), str(pyc.relative_to(path)))

            for mod in zips:
                files = set(mod.glob("**/*.py"))
                files.update(
                    i for i in mod.glob("**/*.pyc")
                    if i.with_suffix(".py") not in files
                )
                for pyc in files:
                    pyc = self.__compile(path, pyc, path)
                    zfile.write(str(pyc), str(pyc.relative_to(path)))

    def __move_files(self, mods, out, path, dll):
        for mod in mods:
            for name in chain(mod.glob('**/*.coffee'), mod.glob("_core"+dll)):
                outp = out/name.relative_to(path)
                outp.parent.mkdir(exist_ok = True, parents = True)
                name.rename(outp)

            for pyc in mod.glob('**/*.py'):
                outp = self.__compile(path, pyc, out)
                if outp == pyc:
                    pyc.rename(out/pyc.relative_to(path))

        for name in path.glob('*'+dll):
            outp = out/name.relative_to(path)
            outp.parent.mkdir(exist_ok = True, parents = True)
            name.rename(outp)

        if (path/self.staticdir).exists():
            (path/self.staticdir).rename(out/self.staticdir)

        for ext in ("js", "sh", "bat"):
            for itm in path.glob("*."+ext):
                itm.rename(out/itm.relative_to(path))

    def __copy_gif(self, path):
        for res in self.resourcepaths:
            if res.endswith(".desktop") and not sys.platform.startswith("win"):
                continue
            src = self.srcnode.find_resource(res)
            tgt = path/Path(res).name
            copy2(src.abspath(), tgt)

    def __final(self, mods):
        path = Path(str(self.options.APP_PATH))
        dll  = '.cp*-win*.pyd' if sys.platform.startswith("win") else '.cpython-*.so'
        mods = [path/Path(mod).name for mod in mods]
        zips = [
            mod for mod in mods
            if (
                mod.exists() and mod.name != self.appdir
                and next(mod.glob("_core"+dll), None) is None
            )
        ]

        out = Path(str(self.options.OUT_PATH))
        if len(zips):
            self.__zip_files(path, out, zips)

        self.__move_files([i for i in mods if i not in zips], out, path, dll)

        final = Path(".")/(("" if self.doall else "patch_")+version())
        if final.exists():
            rmtree(str(final))
        final.mkdir(exist_ok = True, parents = True)
        final = final / self.codedir
        os.rename(str(out), str(final))
        self.__copy_gif(final)

        if (path/self.docdir).exists():
            move(str(path/self.docdir), str(final.parent))

        if Path(self.changelogpath).exists():
            out = final.parent/self.changelogpath
            copy2(self.changelogpath, out)
            try:
                os.system("pandoc --toc -s {} -o {}".format(out, out.with_suffix(".html")))
            except: # pylint: disable=bare-except
                pass

        for i in list(final.glob("*.bat")) + list(final.glob("*.sh")):
            os.rename(str(i), str(final.parent/i.name))
        rmtree(str(path))

    def build_app(self, modules, builder):
        "builds the app"
        self.__clean()
        mods = [i for i in modules(self)
                if not any(j in i for j in self.excluded)]
        builder(self, mods)
        self.recurse(mods, "startscripts", mandatory = False)
        if self.doall:
            node = Path(str(self.bldnode.parent))
            cpy  = Path(str(self.options.OUT_PATH)).relative_to(node)
            _condasetup(self, copy = str(cpy), runtimeonly = True)

        self.add_group()
        self(rule = lambda _: self.__final(mods), always = True)

def package(modules, builder = None, ctxcls = None, **kwa):
    """
    add app packaging functions
    """
    if ctxcls is None:
        ctxcls = basecontext()
    elif isinstance(ctxcls, str):
        ctxcls = basecontext(ctxcls)
    if builder is None:
        builder = getlocals()['build']

    funcs       = lambda x, **y: dict({"fun": x, "cmd": x}, **y)
    _CondaEnv   = type('_CondaEnv', (BuildContext,),  funcs('condaenv'))
    _CondaSetup = type('_CondaSetup', (ctxcls,),      funcs('setup'))
    _CondaApp   = type('_CondaPatch', (AppPackager,), funcs('app', doall = True, **kwa))
    _CondaPatch = type('_CondaPatch', (_CondaApp,),   funcs('apppatch', doall = False))

    def condaenv(cnf):
        u"prints the conda yaml recipe"
        modules(cnf)
        _condaenv(getattr(_CondaApp, 'libname'))

    def setup(cnf):
        "Sets up the python environment"
        modules(cnf)
        _condasetup(cnf)
        if sys.platform.startswith("win"):
            print("COFFEESCRIPT is not mandatory & can be installed manually")

    def app(bld):
        "Creates an application"
        bld.build_app(modules, builder)

    def apppatch(bld):
        "Creates an application patch"
        bld.build_app(modules, builder)

    return dict(
        _CondaEnv   = _CondaEnv,
        _CondaApp   = _CondaApp,
        _CondaPatch = _CondaPatch,
        _CondaSetup = _CondaSetup,
        setup       = setup,
        app         = app,
        apppatch    = apppatch,
        condaenv    = condaenv
    )
