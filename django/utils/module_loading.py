#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @FileName :module_loading.py
# @Author   :Lowell
# @Time     :2022/3/30 17:56
import sys
from importlib import import_module
from importlib.util import find_spec as importlib_find


def cached_import(module_path, class_name):
    if not (
        (module := sys.modules.get(module_path))
        and (spec := getattr(module, "__spec__", None))
        and getattr(spec, "_initializing", False) is False
    ):
        module = import_module(module_path)
    return getattr(module, class_name)


def import_string(dotted_path):
    """
    通过字符串导入模块
    """
    try:
        module_path, class_name = dotted_path.rsplit(".", 1)
    except ValueError as err:
        raise ImportError("%s doesn't look like a module path" % dotted_path) from err

    try:
        return cached_import(module_path, class_name)
    except AttributeError as err:
        raise ImportError(
            'Module "%s" does not define a "%s" attribute/class'
            % (module_path, class_name)
        ) from err


def module_has_submodule(package, module_name):
    try:
        package_name = package.__name__
        package_path = package.__path__
    except AttributeError:
        return False

    full_module_name = package_name + "." + module_name
    try:
        return importlib_find(full_module_name, package_path) is not None
    except ModuleNotFoundError:
        return False
