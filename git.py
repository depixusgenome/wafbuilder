#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"git extraction functions"
from   typing import Any # pylint: disable=unused-import
import os
import subprocess

def _cmd(*args) -> str:
    if any(os.path.exists('../'*i+'.git') for i in range(5)):
        return subprocess.check_output(('git',)+tuple(args)).strip().decode('utf-8')
    else:
        return ''

def version(path = None) -> str:
    u"returns last tag name"
    cmd = 'describe', '--always' # type: Any
    if path is not None:
        commit = _cmd('log', '--format=%H', '-1', '--', str(path))
        cmd   += '--', commit.strip()
    else:
        cmd   +=  '--dirty=+',
    return _cmd(*cmd)

def lasthash() -> str:
    u"returns last commit hashtag"
    return _cmd('log', '-n', '1', '--pretty=format:%H')

def lastdate() -> str:
    u"returns last commit date"
    return _cmd('log', '-n', '1', '--pretty=format:%cD')

def lastauthor() -> str:
    u"returns last commit author"
    return _cmd('log', '-n', '1', '--pretty=format:%an')

def branch() -> str:
    u"returns current branch"
    return _cmd('rev-parse', '--abbrev-ref', 'HEAD')

def isdirty() -> bool:
    u"returns whether we're sitting in-between tags"
    return version()[-1] == '+'
