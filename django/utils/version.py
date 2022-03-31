#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @FileName :version.py
# @Author   :Lowell
# @Time     :2022/3/30 14:13
import datetime
import functools
import os.path
import subprocess


def get_version(version=None):
    """返回一个PEP 440-compliant 版本数字"""
    version = get_complete_version(version)

    # 目前版本由两部分组成
    # main = X.Y[.Z]
    # sub = .devN - for pre-alpha releases
    #     | {a|b|rc}N - for alpha, beta, and rc releases

    main = get_main_version(version)

    sub = ""
    if version[3] == "alpha" and version[4] == 0:
        git_changeset = get_git_changeset()
        if git_changeset:
            sub = ".dev%s" % git_changeset
    elif version[3] != "final":
        mapping = {"alpha": "a", "beta": "b", "rc": "rc"}
        sub = mapping[version[3]] + str(version[4])

    return main + sub


def get_main_version(version=None):
    """
    返回主要版本 (X.Y[.Z])
    """
    version = get_complete_version(version)
    parts = 2 if version[2] == 0 else 3
    return ".".join(str(x) for x in version[:parts])


def get_complete_version(version=None):
    """
    返回django版本元组信息, 如果version非空就检查元组信息正确性
    """
    if version is None:
        from django import VERSION as version
    else:
        assert len(version) == 5
        assert version[3] in ("alpha", "beta", "rc", "final")

    return version


@functools.lru_cache
def get_git_changeset():
    """
    通过git的提交时间戳生成开发版本信息
    """
    if "__file__" not in globals():
        return None
    repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    git_log = subprocess.run(
        "git log --pretty=format:%ct --quiet -1 HEAD",
        capture_output=True,
        shell=True,
        cwd=repo_dir,
        text=True,
    )
    timestamp = git_log.stdout
    tz = datetime.timezone.utc
    try:
        timestamp = datetime.datetime.fromtimestamp(int(timestamp), tz=tz)
    except ValueError:
        return None
    return timestamp.strftime("%Y%m%d%H%M%S")
