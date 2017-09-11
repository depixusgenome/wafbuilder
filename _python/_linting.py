#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"All *basic* python related details"
import sys
from pathlib          import Path
from typing           import Sequence, List  # pylint: disable=unused-import
from pkg_resources    import get_distribution
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
    @staticmethod
    def __pylintrule():
        pylint = ('${PYLINT} ${SRC} '
                  + '--init-hook="sys.path.append(\'./\')" '
                  + '--msg-template="{path}:{line}:{column}:{C}: [{symbol}] {msg}" '
                  + '--disable=locally-disabled '
                  + '--reports=no')

        if get_distribution("pylint").version >= '1.7.1':  # pylint: disable=no-member
            pylint += ' --score=n'

        if (get_distribution("astroid").version == '1.4.8' # pylint: disable=no-member
                or sys.platform.startswith("win")):
            pylint += ' --disable=wrong-import-order,invalid-sequence-index'

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
        def _checkencoding(tsk):
            headers = '#!/usr/bin/env python3\n', '# -*- coding: utf-8 -*-\n'

            with _open(tsk.inputs[0].abspath()) as stream:
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
                bld.fatal('In file %s:\n\t- ' % tsk.inputs[0].abspath()+msg)

        return dict(color       = 'CYAN',
                    rule        = _checkencoding,
                    cls_keyword = lambda _: 'python headers')

    @classmethod
    def run(cls, bld:Context, name:str, items:Sequence):
        "builds tasks for checking code"
        if len(items) == 0:
            return

        pyext = set(bld.env.pyextmodules)
        if any(i.get_name() == name+':pyext' for i in bld.get_all_task_gen()):
            pyext.add(name)

        deps = list(pymoduledependencies(items, name) & pyext)
        def _scan(_):
            nodes = [bld.get_tgen_by_name(dep+':pyext').tasks[-1].outputs[0] for dep in deps]
            return (nodes, [])

        rules = [cls.__encodingrule(bld)] # type: List
        if ('python', 'mypy') in requirements:
            rules.append(cls.__mypyrule())
            rules[-1]['scan'] = _scan
            rules[-1]['group'] = 'mypy'
            if 'mypy' not in bld.group_names:
                bld.add_group('mypy', move = False)

        if ('python', 'pylint') in requirements:
            rules.append(cls.__pylintrule())
            rules[-1]['scan']  = _scan
            rules[-1]['group'] = 'pylint'
            if 'pylint' not in bld.group_names:
                bld.add_group('pylint', move = False)

        def _build(item, kwargs):
            bld(source = [item],
                name   = str(item)+':'+kwargs['cls_keyword'](None).lower(),
                **kwargs)

        if name in deps:
            for _, item in copytargets(bld, name, items):
                for kwargs in rules:
                    _build(item, kwargs)
        else:
            for item in items:
                for kwargs in rules:
                    _build(item, kwargs)

def checkpy(bld:Context, name:str, items:Sequence):
    "builds tasks for checking code"
    return Linting.run(bld, name, items)
