#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"Compiles the JS code once and for all"
import  sys
from    typing     import List
from    importlib  import import_module
from    pathlib    import Path

sys.path.append(str(Path(".").resolve()))
def finddependencies(*modules) -> List[str]:
    "compiles the application as would a normal call to bokeh"
    import  bokeh.util.compiler as _compiler
    for mod in modules:
        import_module(mod)
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
        import_module(mod)

    mdls  = (
        () if bokeh.__version__ == '1.0.4' else
        (getattr(_compiler, '_get_custom_models')(None),)
    )
    string = _compiler.bundle_all_models()
    return f"/*KEY={_compiler.calc_cache_key(*mdls)}*/\n"+string

def build_bokehjs(bld, viewname, key):
    "build the js file"
    modules = list(bld.env.BOKEH_DEFAULT_MODULES)
    parts   = viewname.split('.')
    for i, j  in enumerate(parts):
        if j[0] == j[0].upper():
            break
        modules.append('.'.join(parts[:i+1]))

    paths = bld.env.BOKEH_DEFAULT_JS_PATHS
    root  = Path(str(bld.launch_dir))
    for i in sum((list(Path(j).glob('**/*.py')) for j in paths), []):
        if i.name[:2] == '__':
            continue

        i = str(i.relative_to(root))[:-3].replace("/", ".").replace("\\", ".")
        modules.append( i[i.find(".")+1:])

    modules = [i for i in modules if i[:2] != '__']
    mods    = [i.split('.')[0] for i in modules]
    mods    = [j for i, j in enumerate(mods) if j not in mods[:i]]
    srcs    = []
    for i in mods:
        for j in ('ts', 'coffee'):
            srcs.extend(root.glob(f"*/{i.replace('.', '/')}/**/*.{j}"))

    from wafbuilder import copyroot
    tgt  = copyroot(bld, key+'.js')

    rule = f'{bld.env["PYTHON"][0]} {__file__} '+' '.join(modules)+' -o ${TGT} -k '+key
    bld(
        source       = [bld.srcnode.find_node(str(k.relative_to(root))) for k in srcs],
        name         = modules[0]+':bokeh',
        color        = 'BLUE',
        rule         = rule,
        target       = tgt,
        cls_keyword  = lambda _: 'Bokeh',
        group        = 'bokeh',
        **bld.installcodepath()
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
