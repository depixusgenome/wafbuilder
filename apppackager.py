#!/usr/bin/env python3
# encoding: utf-8
"Everything related to conda"
import sys
from pathlib import Path

from waflib           import TaskGen
from waflib.Configure import conf

from ._python         import condasetup as _condasetup
from ._utils          import CODE_PATH, copyfiles
from .bokehcompiler   import build_bokehjs
from .git             import version as _version
from .modules         import basecontext

def build_resources(bld):
    "install resources in installation directory"
    files = bld.path.ant_glob([i+"/**/static/*."+j
                               for j in ("css", "js", "map", "svg", "eot",
                                         "ttf", "woff")
                               for i in bld.env.MODULE_SOURCE_DIR])
    copyfiles(bld, 'static', files)
    bld.install_files(
        bld.installcodepath("static", direct = True),
        files
    )

    src = [i for i in bld.env.APP_RESOURCES]
    if sys.platform.startswith("win"):
        src = [i for i in src if not str(i).endswith(".desktop")]

    bld.install_files(
        bld.installpath(direct = True),
        [bld.root.find_node(i) for i in src],
    )

def install_condaenv(bld):
    "install conda env in installation directory"
    dist = Path(str(bld.env.PREFIX))/bld.env.DISTRIBUTION_PATH
    if not (dist/"conda-meta").exists():
        node = Path(str(bld.bldnode.parent))
        _condasetup(bld, copy = str(dist.relative_to(node)), runtimeonly = True)

def build_changelog(bld):
    "build the changelog"
    chlog = "CHANGELOG.md" if not bld.env.CHANGELOG_PATH else bld.env.CHANGELOG_PATH
    if Path(chlog).exists():
        bld(source = [bld.srcnode.find_node(chlog)])

def build_startupscripts(bld, name, scriptname):
    "creates the startup script"
    iswin = sys.platform.startswith("win")
    ext   = ".bat" if iswin else ".sh"
    args  = dict(
        features   = "subst",
        code       = bld.env.CODE_PATH,
        distrib    = bld.env.DISTRIBUTION_PATH,
        scriptname = scriptname,
        target     = bld.bldnode.find_or_declare("bin/"+name+ext),
        source     = bld.srcnode.find_resource(f"{__package__}/_exec{ext}"),
        **bld.installpath()
    )
    for cmdline, debug in bld.env.CMDLINES:
        args['cmdline'] = cmdline
        if iswin:
            bld(**dict(
                args,
                target = bld.bldnode.find_or_declare("bin/"+name+("_debug" if debug else "")+ext),
                start  = r'start /min' if debug else r"",
                python = r'pythonw'    if debug else r"python",
                pause  = "pause"       if debug else r""
            ))
        elif not debug:
            bld(**args)

def build_doc(bld, scriptname):
    "create the doc"
    path = bld.env.table.get('DOCPATH', "doc")
    if not (
            'SPHINX_BUILD' in bld.env
            and (Path(str(bld.srcnode))/path/scriptname).exists()
    ):
        return

    target = str(bld.bldnode)+f"/{path}/"+scriptname
    rule   = (
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

def package(glob, modulelist, **kwa):
    """
    add app packaging functions
    """
    funcs       = lambda x, **y: dict({"fun": x, "cmd": x}, **y)
    _CondaSetup = type('_CondaSetup', (basecontext(),),      funcs('setup'))

    def setup(cnf):
        "Sets up the python environment"
        modulelist(cnf)
        _condasetup(cnf)

    def configure(cnf, __old__  = glob['configure']):
        "Adds options to the configuration"
        configure_app(cnf, **kwa)
        __old__(cnf)

    def options(opt, __old__  = glob['options']):
        "Adds options to the configuration"
        options_app(opt)
        __old__(opt)

    glob.update(dict(
        _CondaSetup = _CondaSetup,
        setup       = setup,
        options     = options,
        configure   = configure
    ))

def guimake(viewname, locs, scriptname = None):
    "default make for a gui"
    from wafbuilder import make
    make(locs)
    def guibuild(cnf, __old__ = locs['build']):
        "build gui"
        __old__(cnf)
        build_app(cnf, locs['APPNAME'], viewname, scriptname)
    locs["build"] = guibuild

@conf
def options_app(opt):
    "configure app options"
    grp = opt.add_option_group('Configuration options')
    grp.add_option(
        '--fulldist',
        dest    = 'ispatch',
        action  = 'store_false',
        default = True,
        help    = "Whether we are creating a patch or a full distribution"
    )

@conf
def configure_app(cnf, cmds = (), modules = (), jspaths = (), resources = ()):
    "configure bokehjs"
    cnf.find_program("sphinx-build", var="SPHINX_BUILD", mandatory=False)
    cnf.find_program("pandoc", var="PANDOC", mandatory=False)
    cnf.env.DOCPATH           = "doc"
    cnf.env.CODE_PATH         = CODE_PATH
    cnf.env.DISTRIBUTION_PATH = "distribution"
    cnf.env.ISPATCH           = cnf.options.ispatch
    cnf.env.PREFIX            = str(
        Path(str(cnf.bldnode))
        /(('patch_' if cnf.options.ispatch else '')+_version())
    )

    cnf.env.append_value("BOKEH_DEFAULT_MODULES", list(modules))
    cnf.env.append_value(
        "BOKEH_DEFAULT_JS_PATHS",
        [str(cnf.srcnode.find_node(i)) for i in jspaths]
    )
    cnf.env.append_value("CMDLINES", list(cmds))
    cnf.env.append_value(
        "APP_RESOURCES",
        [str(cnf.srcnode.find_node(i)) for i in resources]
    )

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

def build_app(bld, appname, viewname, scriptname = None):
    "build gui"
    name = appname if scriptname is None else scriptname
    build_startupscripts(bld, name, appname+'.'+viewname)
    build_bokehjs(bld, viewname, scriptname)
    build_doc(bld, scriptname)
    if bld.env.PANDOC:
        TaskGen.declare_chain(
            name         = 'markdowns',
            rule         = '${PANDOC} --toc -s ${SRC} -o ${TGT}',
            ext_in       = '.md',
            ext_out      = '.html',
            shell        = False,
            reentrant    = False,
            **bld.installpath()
        )

__builtins__['guimake'] = guimake # type: ignore
