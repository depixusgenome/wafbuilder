#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Compiles the JS code once and for all"
import  sys
from    typing     import List
from    pathlib    import Path

sys.path.append(str(Path(".").resolve()))
def finddependencies(*modules) -> List[str]:
    "compiles the application as would a normal call to bokeh"
    import  bokeh.util.compiler as _compiler
    for mod in modules:
        __import__(mod)
    old = _compiler.nodejs_compile
    lst = []
    def _deps(_1, lang="javascript", file=None): # pylint: disable=unused-argument
        lst.append(file)
        return _compiler.AttrDict({'code': '', 'deps': []})
    _compiler.nodejs_compile = _deps
    _compiler.bundle_all_models()
    _compiler.nodejs_compile = old
    return lst

def compileapp(*modules) -> str:
    "compiles the application as would a normal call to bokeh"
    import  bokeh.util.compiler as _compiler
    for mod in modules:
        __import__(mod)
    string = _compiler.bundle_all_models()
    return f"/*KEY={_compiler.calc_cache_key()}*/\n"+string

class GuiMaker:
    "make gui"
    def __init__(self, **kwa):
        self.modules     = ('taskview.toolbar', 'undo')
        self.modulepaths = ('core/app', 'core/view')
        self.docpath     = "doc"
        self.cmdlines    = (
            (r'taskapp/cmdline.pyc --port random -g app ',      False),
            (r'taskapp/cmdline.pyc --port random -g browser ',  True),
        )
        self.__dict__.update(kwa)

    def __call__(self, viewname, locs, scriptname = None):
        "default make for a gui"
        name = locs['APPNAME'] if scriptname is None else scriptname

        if 'startscripts' not in locs:
            def startscripts(bld):
                "creates start scripts"
                val = r" "+locs['APPNAME']+'.'+viewname
                for cmd, debug in self.cmdlines:
                    self.build_startupscripts(bld, name, cmd+val, debug)
            locs['startscripts'] = startscripts

        old = locs.pop('build')
        def build(bld):
            "build gui"
            old(bld)
            paths = [bld.bldnode.parent.find_node(i) for i in self.modulepaths]
            mods  = list(self.modules)+[locs['APPNAME']]
            self.build_bokehjs(bld, viewname, mods, paths, scriptname)
            self.build_doc(bld, scriptname, self.docpath)

        locs['build'] = build

    @staticmethod
    def build_startupscripts(bld, name, cmdline, debug = False, path = None):
        "creates the startup script"
        if path is None:
            path = getattr(bld.options, 'APP_PATH', bld.bldnode)

        iswin = sys.platform.startswith("win")
        ext   = ".bat" if iswin else ".sh"
        if iswin:
            cmd  = (
                'cd code\r\n'
                'SET "PATH=%~dp0\\code\\Library\\bin;%PATH%"\r\n'
            )
            cmd += (
                r'%~dp0\code\python -I '                if debug else
                r'start /min %~dp0\code\pythonw -I '
            )
        else:
            cmd = (
                r'IR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"\n'
                r'cd $DIR/code\n'
                r'./bin/python'
            )

        fname = str(path.make_node(name+("_debug" if debug else "")+ext))
        with open(fname, 'w', encoding = 'utf-8') as stream:
            print(cmd + r" "+ cmdline, file = stream)
            if debug and iswin:
                print(r"pause", file = stream)

    @staticmethod
    def build_bokehjs(bld, viewname, modules, paths, key):
        "build the js file"
        if '.' in viewname:
            for i in viewname.split('.'):
                if i[0] == i[0].upper():
                    break
                modules.append(modules[-1]+'.'+i)

        for i in sum((j.ant_glob('**/*.py') for j in paths), []):
            i = i.srcpath()
            if Path(str(i)).name[:2] != '__':
                modules.append(str(i)[5:-3].replace("/", ".").replace("\\", "."))

        modules = [i for i in modules if i[:2] != '__']
        root    = bld.path.ctx.bldnode
        mods    = [i.split('.')[0] for i in modules]
        mods    = [j for i, j in enumerate(mods) if j not in mods[:i]]
        srcs    = sum((root.ant_glob(i.replace('.', '/')+'/**/*.coffee') for i in mods), [])

        from wafbuilder import copyroot
        tgt  = copyroot(bld, key+'.js')

        rule = f'{bld.env["PYTHON"][0]} {__file__} '+' '.join(modules)+' -o ${TGT} -k '+key
        root = Path(str(bld.run_dir)).stem+"/"
        bld(source       = srcs,
            name         = modules[0]+':bokeh',
            color        = 'BLUE',
            rule         = rule,
            target       = tgt,
            cls_keyword  = lambda _: 'Bokeh',
            install_path = '${PYTHONARCHDIR}/'+root,
            group        = 'bokeh')

    @staticmethod
    def build_doc(bld, scriptname, path = 'doc'):
        "create the doc"
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
            '${PYTHONARCHDIR}/'+Path(str(bld.run_dir)).stem+"/doc",
            tgt.parent.ant_glob("**/*.*"),
            cwd            = tgt.parent,
            relative_trick = True
        )

    @classmethod
    def run(cls, viewname, locs, scriptname = None, **kwa):
        "run this class"
        cls(**kwa)(viewname, locs, scriptname)

if __name__ == '__main__':
    # pylint: disable=no-value-for-parameter
    import click
    @click.command()
    @click.argument('modules', nargs = -1)
    @click.option("-o", "--output", type = click.Path(), default = None)
    @click.option("-d", "--dependencies", flag_value = True, default = False)
    @click.option("-k", "--key", default = "")
    def _main(modules, output, dependencies, key):
        if dependencies:
            string = '\n'.join(finddependencies(*modules))
        else:
            string = compileapp(*modules)

        if output is None:
            print(string)
        else:
            if key == "":
                key = Path(output).stem
            print(f"/*KEY={key}*/\n"+string,
                  file = open(output, 'w', encoding='utf-8'))

    _main()
