#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @FileName :config.py
# @Author   :Lowell
# @Time     :2022/3/30 16:42
import inspect
import os
from importlib import import_module

from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import module_has_submodule, import_string

APPS_MODULE_NAME = "apps"
MODELS_MODULE_NAME = "models"


class AppConfig:
    """Django应用程序及其配置"""

    def __init__(self, app_name, app_module):
        # 应用程序的完整python路径, 例如`django.contrib.admin`
        self.name = app_name

        # 应用程序的根模块
        # `<module 'django.contrib.admin from 'django/contrib/admin/__init__.py''>`
        self.module = app_module

        # 对保存此AppConfig的应用程序注册表的引用
        # 注册AppConfig实例时由注册表设置
        self.apps = None

        # 以下的属性可以在子类中定义, 由此的测试和设置模式

        # 应用程序在python路径的最后一个组件, 比如`django.contrib.admin`中的`admin`
        # 这个值在整个django应用中必须唯一
        if not hasattr(self, "label"):
            self.label = app_name.rpartition(".")[2]
        if not self.label.isidentifier():
            raise ImproperlyConfigured(
                "The app label '%s' is not a valid Python identifier." % self.label
            )

        # 应用程序中可读的名称, 例如`Admin`
        if not hasattr(self, "verbose_name"):
            self.verbose_name = self.label.title()

        # 文件路径
        if not hasattr(self, "path"):
            self.path = self._path_from_module(app_module)

        # 包含模型的模块, 将在import_models()时设置, 如果模块没有模型就置为空
        self.models_module = None

        # 将小写的模型名称映射到模型类, 初始化设置为None, 以阻止在import_models()前意外访问
        self.models = None

    def __repr__(self):
        return "<%s: %s>" % (self.__class__.__name__, self.label)

    def _path_from_module(self, module):
        """尝试从其模块获取app应用的文件路径"""
        # 转换为列表, __path__可能不支持索引
        paths = list(getattr(module, "__path__", []))
        if len(paths) != 1:
            filename = getattr(module, "__file__", None)
            if filename is not None:
                paths = [os.path.dirname(filename)]
            else:
                # 有时候__path__会出现重复的 (#25246)
                paths = list(set(paths))
        if len(paths) > 1:
            # 如果有多个文件目录, 需要重写AppConfig, 并设置path属性
            raise ImproperlyConfigured(
                "The app module %r has multiple filesystem locations (%r); "
                "you must configure this app with an AppConfig subclass "
                "with a 'path' class attribute." % (module, paths)
            )
        elif not paths:
            raise ImproperlyConfigured(
                "The app module %r has no filesystem location, "
                "you must configure this app with an AppConfig subclass "
                "with a 'path' class attribute." % module
            )
        return paths[0]

    @classmethod
    def create(cls, entry):
        """
        从INSTALLED_APPS中创建app config的工厂
        """
        # 最终返回app_config_class(app_name, app_module).
        app_config_class = None
        app_name = None
        app_module = None

        # 如果import_module成功, 就进入应用程序模块
        try:
            app_module = import_module(entry)
        except Exception:
            pass
        else:
            if module_has_submodule(app_module, APPS_MODULE_NAME):
                mod_path = "%s.%s" % (entry, APPS_MODULE_NAME)
                mod = import_module(mod_path)
                # 排除那些定义`default=False`的app配置
                app_configs = [
                    (name, candidate)
                    for name, candidate in inspect.getmembers(mod, inspect.isclass)
                    if (
                        issubclass(candidate, cls)
                        and candidate is not classmethod
                        and getattr(candidate, "default", True)
                    )
                ]
                if len(app_configs) == 1:
                    app_config_class = app_configs[0][1]
                else:
                    # 检查是否是有一个AppConfig子类, 并明确定义了`default=True`
                    app_configs = [
                        (name, candidate)
                        for name, candidate in app_configs
                        if getattr(candidate, "default", False)
                    ]
                    if len(app_configs) > 1:
                        candidates = [repr(name) for name, _ in app_configs]
                        raise RuntimeError(
                            "%r declares more than one default AppConfig: "
                            "%s." % (mod_path, ", ".join(candidates))
                        )
                    elif len(app_configs) == 1:
                        app_config_class = app_configs[0][1]

            # 如果没找到就是用默认的app配置
            if app_config_class is None:
                app_config_class = cls
                app_name = entry

        if app_config_class is None:
            try:
                app_config_class = import_string(entry)
            except Exception:
                pass

        # 如果import_module和import_string都失败了, 就说明这个entry不是个有效值
        if app_module is None and app_config_class is None:
            # 如果entry的最后一个组件比如`django.contrib.admin`中的`admin`, 开头是大写字母
            # 那么很可能是一个app配置类, 否则是一个app模块
            # 为这两种情况给一个清晰的提错误信息
            mod_path, _, cls_name = entry.rpartition(".")
            if mod_path and cls_name[0].isupper():
                mod = import_module(mod_path)
                candidates = [
                    repr(name)
                    for name, candidate in inspect.getmembers(mod, inspect.isclass)
                    if issubclass(candidate, cls) and candidate is not cls
                ]
                msg = "Module '%s' does not contain a '%s' class." % (
                    mod_path,
                    cls_name,
                )
                if candidates:
                    msg += " Choices are: %s." % ", ".join(candidates)
                raise ImportError(msg)
            else:
                # 如果是模块就试着重新导入触发模块导入异常
                import_module(entry)

        # 阻止通过鸭子类型type创建的配置类, 允许在实践中移除
        if not issubclass(app_config_class, AppConfig):
            raise ImproperlyConfigured("'%s' isn't a subclass of AppConfig." % entry)

        # 在此处而不是在AppClass.__init__中获取app名称
        # 保证所有INSTALLED_APPS的检查出现的错误只在一处发生
        if app_name is None:
            try:
                app_name = app_config_class.name
            except AttributeError:
                raise ImproperlyConfigured("'%s' must supply a name attribute." % entry)

        # 确保app_name是一个有效模块
        try:
            app_module = import_module(app_name)
        except ImportError:
            raise ImproperlyConfigured(
                "Cannot import '%s'. Check that '%s.%s.name' is correct."
                % (
                    app_name,
                    app_config_class.__module__,
                    app_config_class.__qualname__,
                )
            )

        # 返回一个AppConfig类
        return app_config_class(app_name, app_module)

    def import_models(self):
        self.models = self.apps.all_models[self.label]

        if module_has_submodule(self.module, MODELS_MODULE_NAME):
            models_module_name = "%s.%s" % (self.name, MODELS_MODULE_NAME)
            self.models_module = import_module(models_module_name)

