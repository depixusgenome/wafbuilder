#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"All *basic* python related details"
import sys
import re
from pathlib          import Path
from typing           import Sequence, List  # pylint: disable=unused-import
from waflib.Context   import Context
from .._requirements  import REQ as requirements
from .._utils         import copytargets
from ._pybind11       import pymoduledependencies

_open = lambda x: open(x, 'r', encoding = 'utf-8')
requirements.addcheck(requirements.programversion, lang = 'python', name = 'pylint')

@requirements.addcheck
def check_python_astroid(cnf, name, version):
    "checks pylint's astroid version"
    requirements.programversion(cnf, 'pylint', version, reg = name)

@requirements.addcheck
def check_python_mypy(cnf, name, version):
    "checks python's mypy"
    requirements.programversion(cnf, name, version)
    cmd = getattr(cnf.env, name.upper())+ ["--version"]
    if float(cnf.cmd_and_log(cmd).split()[1]) <= 0.501:
        cnf.env[name.upper()] += ['--fast-parser']

    cmd = getattr(cnf.env, name.upper()) + ["-c", '"print(1)"']
    cnf.cmd_and_log(cmd)

class Linting:
    "all rules for checking python"
    INCLUDE_PYEXTS = False
    @classmethod
    def run(cls, bld:Context, name:str, items:Sequence, *discards):
        "builds tasks for checking code"
        if bld.options.DO_PY_LINTING is False or len(items) == 0 or bld.cmd != 'build':
            return

        deps  = cls.__make_deps(bld, name, items)
        rules = cls.__make_rules(bld, deps, discards)

        if name in deps:
            items = [i for _, i in copytargets(bld, name, items)]

        for item in items:
            for kwargs in rules:
                bld(source = [item],
                    name   = str(item)+':'+kwargs['cls_keyword'](None).lower(),
                    **kwargs)

    @staticmethod
    def options(opt: Context):
        "add options"
        return (
            opt
            .add_option_group("Python Options")
            .add_option(
                "--nolinting",
                help    = "Discard linting jobs",
                default = True,
                dest    = "DO_PY_LINTING",
                action  = "store_false",
            )
        )

    @staticmethod
    def __pylintrule():
        crlf   = '' if sys.platform == 'linux' else ',unexpected-line-ending-format'
        pylint = ('${PYLINT} ${SRC} '
                  + '--msg-template="{path}:{line}:{column}:{C}: [{symbol}] {msg}" '
                  + '--disable=locally-disabled,fixme%s ' % crlf
                  + '--reports=no '
                  + '--score=n'
                  )

        for name in ('', 'linting', '..', '../linting'):
            path = Path(name)/'pylintrc'
            if path.exists():
                pylint += ' --rcfile="'+str(path.resolve())+'"'
                break

        return dict(color       = 'YELLOW',
                    rule        = pylint,
                    cls_keyword = lambda _: 'PyLint')

    @staticmethod
    def __mypyrule():
        mypy   = ('${MYPY} ${SRC}  --ignore-missing-imports '
                  +'--follow-imports=skip')
        for name in ('', 'linting', '..', '../linting'):
            path = Path(name)/'mypy.ini'
            if path.exists():
                mypy += ' --config-file="'+str(path.resolve())+'"'
                break
        return dict(color       = 'BLUE',
                    rule        = mypy,
                    cls_keyword = lambda _: 'MyPy')

    @staticmethod
    def __encodingrule(bld):
        fixme = re.compile(r".*#\s*(FIXME|TODO|DEBUG).*")
        def _checkencoding(tsk):
            headers = '#!/usr/bin/env python3\n', '# -*- coding: utf-8 -*-\n'
            abspath = tsk.inputs[0].abspath()

            with _open(abspath) as stream:
                errs    = [True]*2
                try:
                    for i, head in enumerate(headers):
                        errs[i] = next(stream) != head
                except IOError as ex:
                    bld.fatal("Could not open file", ex)
                except StopIteration:
                    pass

            tpl = 'Missing or incorrect header line %d: '
            msg = '\t- '.join((tpl % i + headers[i])  for i in range(len(errs)) if errs[i])
            if len(msg):
                bld.fatal(f'In file {abspath}:\n\t- {msg}')

            with _open(tsk.inputs[0].abspath()) as stream:
                for i, line in enumerate(stream):
                    match = fixme.match(line)
                    if match:
                        bld.to_log(f'\n{abspath}|{i} col 1 warning| [{match.group(1)}]\n`')

        return dict(color       = 'CYAN',
                    rule        = _checkencoding,
                    cls_keyword = lambda _: 'python headers')

    @classmethod
    def __make_deps(cls, bld:Context, name:str, items:Sequence) -> List:
        if cls.INCLUDE_PYEXTS:
            pyext = set(bld.env.pyextmodules)
            if any(i.get_name() == name+':pyext' for i in bld.get_all_task_gen()):
                pyext.add(name)

            return list(pymoduledependencies(items, name) & pyext)
        return []

    @classmethod
    def __make_rules(cls, bld, deps, discards) -> list:
        def _scan(_):
            nodes = [bld.get_tgen_by_name(dep+':pyext').tasks[-1].outputs[0] for dep in deps]
            return (nodes, [])

        rules = [cls.__encodingrule(bld)] # type: List
        if ('python', 'mypy') in requirements and 'mypy' not in discards:
            rules.append(cls.__mypyrule())
            rules[-1]['scan']  = _scan
            rules[-1]['group'] = 'mypy'
            if 'mypy' not in bld.group_names:
                bld.add_group('mypy', move = False)

        if ('python', 'pylint') in requirements and 'pylint' not in discards:
            rules.append(cls.__pylintrule())
            rules[-1]['scan']  = _scan
            rules[-1]['group'] = 'pylint'
            if 'pylint' not in bld.group_names:
                bld.add_group('pylint', move = False)
        return rules

def checkpy(bld:Context, name:str, items:Sequence, *discards):
    "builds tasks for checking code"
    return Linting.run(bld, name, items, *discards)
