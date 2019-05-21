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
    import bokeh
    import bokeh.util.compiler as _compiler
    for mod in modules:
        __import__(mod)

    mdls  = (
        () if bokeh.__version__ == '1.0.4' else
        (getattr(_compiler, '_get_custom_models')(None),)
    )
    string = _compiler.bundle_all_models()
    return f"/*KEY={_compiler.calc_cache_key(*mdls)}*/\n"+string

def build_bokehjs(bld, viewname, key):
    "build the js file"
    modules = list(bld.env.BOKEH_DEFAULT_MODULES)
    if '.' in viewname:
        for i in viewname.split('.'):
            if i[0] == i[0].upper():
                break
            modules.append(modules[-1]+'.'+i)

    paths = bld.env.BOKEH_DEFAULT_JS_PATHS
    for i in sum((j.ant_glob('**/*.py') for j in paths), []):
        i = i.srcpath()
        if Path(str(i)).name[:2] != '__':
            modules.append(str(i)[5:-3].replace("/", ".").replace("\\", "."))

    modules = [i for i in modules if i[:2] != '__']
    root    = bld.path.ctx.bldnode
    mods    = [i.split('.')[0] for i in modules]
    mods    = [j for i, j in enumerate(mods) if j not in mods[:i]]
    srcs    = sum((root.ant_glob(i.replace('.', '/')+'/**/*.coffee') for i in mods), [])
    srcs   += sum((root.ant_glob(i.replace('.', '/')+'/**/*.ts') for i in mods), [])

    from wafbuilder import copyroot
    tgt  = copyroot(bld, key+'.js')

    rule = f'{bld.env["PYTHON"][0]} {__file__} '+' '.join(modules)+' -o ${TGT} -k '+key
    bld(
        source       = srcs,
        name         = modules[0]+':bokeh',
        color        = 'BLUE',
        rule         = rule,
        target       = tgt,
        cls_keyword  = lambda _: 'Bokeh',
        group        = 'bokeh'
        **bld.installpath("code")
    )

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
