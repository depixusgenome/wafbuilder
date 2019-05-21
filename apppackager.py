#!/usr/bin/env python3
# encoding: utf-8
"Everything related to conda"
import sys
import os
from pathlib            import Path
from itertools          import chain
from zipfile            import ZipFile
from shutil             import rmtree, copy2, move
from typing             import List, Dict, Union
import py_compile

from waflib             import TaskGen
from waflib.Build       import BuildContext
from waflib.Configure   import conf

from .git           import version
from .bokehcompiler import build_bokehjs
from .modules       import basecontext
from ._python       import condasetup as _condasetup
from ._utils        import copyfiles

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
            for name in chain(
                    mod.glob('**/*.coffee'),
                    mod.glob('**/*.ts'),
                    mod.glob("_core"+dll)
            ):
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

def build_resources(bld):
    "install resources in installation directory"
    files = bld.path.ant_glob([i+"/**/static/*."+j
                               for j in ("css", "js", "map", "svg", "eot",
                                         "ttf", "woff")
                               for i in bld.env.MODULE_SOURCE_DIR])
    copyfiles(bld, 'static', files)
    bld.install_files(
        bld.installpath("static", direct = True),
        files
    )

    src = [str(bld.root)+"/"+str(i) for i in bld.env.RESOURCES]
    if sys.platform.startswith("win"):
        src = [i for i in src if not i.endswith(".desktop")]

    bld.install_files(
        bld.installpath(direct = True),
        src,
        cwd            = bld.root,
        relative_trick = True
    )

def install_condaenv(bld):
    "install conda env in installation directory"
    node = Path(str(bld.bldnode.parent))
    cpy  = Path(str(bld.env.PREFIX)).relative_to(node)
    _condasetup(bld, copy = str(cpy), runtimeonly = True)

def build_changelog(bld):
    "build the changelog"
    chlog = "CHANGELOG.md" if not bld.env.CHANGELOG_PATH else bld.env.CHANGELOG_PATH
    if Path(chlog).exists():
        bld(source = [bld.root.find_or_declare(chlog)])

def build_startupscripts(bld, name, scriptname):
    "creates the startup script"
    iswin = sys.platform.startswith("win")
    ext   = ".bat" if iswin else ".sh"
    args  = dict(
        features   = "subst",
        directory  = "code",
        scriptname = scriptname,
        target     = "bin/"+name+ext,
        source     = bld.srcnode.find_resource(f"{__package__}/_exec{ext}")
        **bld.installpath()
    )
    for cmdline in bld.env.table.get('CMDLINES', []):
        args['cmdline'] = cmdline
        if iswin:
            bld(
                start  = r'start /min',
                python = r'pythonw',
                pause  = "",
                **args
            )
            bld(**dict(
                args,
                target = "bin"/name+"_debug"+ext,
                start  = r'',
                python = r'python',
                pause  = "pause"
            ))
        else:
            bld(python = r'./bin/python', **args)

def build_doc(bld, scriptname):
    "create the doc"
    path = bld.env.table.get('DOCPATH', "doc")
    if not (
            'SPHINX_BUILD' in bld.env
            and (Path(str(bld.srcnode))/path/scriptname).exists()
    ):
        return
    if getattr(bld.options, 'APP_PATH', None) is None:
        target = str(bld.bldnode)+f"/{path}/"+scriptname
    else:
        target = str(bld.options.APP_PATH)+f"/{path}/"+scriptname

    rule = (
        "${SPHINX_BUILD} "+str(bld.srcnode)+f"/{path}/{scriptname} "
        +"-c "+str(bld.srcnode)+f"/{path} "
        +target
        + f" -D master_doc={scriptname} -D project={scriptname} -q"
    )

    tgt = bld.path.find_or_declare(target+f'/{scriptname}.html')
    bld(
        rule   = rule,
        source = (
            bld.srcnode.ant_glob(f'{path}/{scriptname}/*.rst')
            + bld.srcnode.ant_glob(path+'/conf.py')
        ),
        target = tgt
    )
    bld.install_files(
        bld.installpath(path, direct = True),
        tgt.parent.ant_glob("**/*.*"),
        cwd            = tgt.parent,
        relative_trick = True
    )

def package(modules):
    """
    add app packaging functions
    """
    funcs       = lambda x, **y: dict({"fun": x, "cmd": x}, **y)
    _CondaSetup = type('_CondaSetup', (basecontext(),),      funcs('setup'))

    def setup(cnf):
        "Sets up the python environment"
        modules(cnf)
        _condasetup(cnf)
    return dict(_CondaSetup = _CondaSetup, setup = setup)

def guimake(viewname, locs, scriptname = None):
    "default make for a gui"
    from wafbuilder import make
    make(locs)
    def guibuild(cnf, __old__ = locs['build']):
        "build gui"
        __old__(cnf)
        cnf.build_app(locs['APPNAME'], viewname, scriptname)
    locs["build"] = guibuild

@conf
def configure_app(cnf, cmds = (), modules = (), jspaths = (), resources = ()):
    "configure bokehjs"
    cnf.find_program("sphinx-build", var="SPHINX_BUILD", mandatory=False)
    cnf.env.DOCPATH = "doc"
    cnf.env.ISPATCH = cnf.env.ispatch
    for i in modules:
        cnf.env.append_value("BOKEH_DEFAULT_MODULES", i)

    for i in jspaths:
        cnf.env.append_value("BOKEH_DEFAULT_JS_PATHS", i)

    for i in cmds:
        cnf.env.append_value("CMDLINES", i)

    for i in resources:
        cnf.env.append_value("RESOURCES", i)

@conf
def build_appenv(bld):
    "install general app stuff"
    build_resources(bld)
    build_changelog(bld)
    bld.build_python_version_file()
    bld.add_group('bokeh', move = False)
    if bld.env.ISPATCH or bld.cmd != "install":
        return
    install_condaenv(bld)

@conf
def installpath(*names, direct = False) -> Union[str, Dict[str, str]]:
    "return the install path"
    path = '{PREFIX}/'+'/'.join(names)
    return path if direct else {"install_path": path}

TaskGen.declare_chain(
    name         = 'markdowns',
    rule         = '${PANDOC} --toc -s ${SRC} -o ${TGT}',
    ext_in       = '.md',
    ext_out      = '.html',
    shell        = False,
    reentrant    = False,
    **installpath()
)

@conf
def build_app(bld, appname, viewname, scriptname = None):
    "build gui"
    name = appname if scriptname is None else scriptname
    build_startupscripts(bld, name, appname+'.'+viewname)
    build_bokehjs(bld, viewname, scriptname)
    build_doc(bld, scriptname)

__builtins__['guimake'] = guimake # type: ignore
