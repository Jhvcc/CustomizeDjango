#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @FileName :autoreload.py
# @Author   :Lowell
# @Time     :2022/3/30 14:12
import functools
import sys
import traceback


_error_files = []
_exception = None


def check_errors(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        global _exception
        try:
            fn(*args, **kwargs)
        except Exception:
            _exception = sys.exc_info()

            et, ev, tb = _exception

            if getattr(ev, "filename", None) is None:
                # 从栈中获取最后一项的文件名
                filename = traceback.extract_tb(tb)[-1][0]
            else:
                filename = ev.filename

            if filename not in _error_files:
                _error_files.append(filename)
            raise

    return wrapper

