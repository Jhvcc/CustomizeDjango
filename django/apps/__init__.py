#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @FileName :__init__.py.py
# @Author   :Lowell
# @Time     :2022/3/30 16:13

from .config import AppConfig
from .registry import apps


__all__ = ["AppConfig", "apps"]
