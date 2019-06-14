#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"git extraction functions"
from   typing import Any # pylint: disable=unused-import
import os
import subprocess

def _cmd(*args) -> str:
    if any(os.path.exists('../'*i+'.git/refs/heads/master') for i in range(5)):
        return (subprocess.check_output(('git',)+tuple(args),
                                        stderr = subprocess.DEVNULL)
                .strip().decode('utf-8'))
    else:
        return ''

def version(path = None) -> str:
    u"returns last tag name"
    cmd = 'describe', '--always' # type: Any
    if path is not None:
        commit = _cmd('log', '--format=%H', '-1', '--', str(path))
        if len(commit.strip()):
            cmd   += '--', commit.strip()
    else:
        cmd   +=  ('--dirty=+',)
    return _cmd(*cmd)

def origin() -> str:
    u"returns origin repo name"
    cmd = 'remote', 'get-url', 'origin' # type: Any
    out = _cmd(*cmd)
    return out.replace('\\', '/').split('/')[-1].split('.')[0]

def lasthash(path = None) -> str:
    u"returns last commit hashtag"
    if path is not None:
        return _cmd('log', '--format=%h', '-1', '--', str(path))
    return _cmd('log', '-n', '1', '--pretty=format:%H')

def lasttimestamp(path = None) -> str:
    u"returns last commit timestamp"
    if path is not None:
        return _cmd('log', '--format=%at', '-1', '--', str(path))
    return _cmd('log', '-n', '1', '--pretty=format:%at')

def lastdate() -> str:
    u"returns last commit date"
    return _cmd('log', '-n', '1', '--pretty=format:%cD')

def lastauthor() -> str:
    u"returns last commit author"
    return _cmd('log', '-n', '1', '--pretty=format:%an')

def branch() -> str:
    u"returns current branch"
    return _cmd('rev-parse', '--abbrev-ref', 'HEAD')

def isdirty(path = None) -> bool:
    u"returns whether we're sitting in-between tags"
    vers = version(path)
    return vers[-1] == '+' if vers else False
