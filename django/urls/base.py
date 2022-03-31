#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @FileName :base.py
# @Author   :Lowell
# @Time     :2022/3/30 13:00
from asgiref.local import Local

_prefixes = Local()


def set_script_prefix(prefix):
    """

    """
    if not prefix.endswith("/"):
        prefix += "/"
    _prefixes.values = prefix


def get_script_prefix():
    """

    """
    return getattr(_prefixes, "value", "/")

