#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @FileName :registry.py
# @Author   :Lowell
# @Time     :2022/3/30 16:13
import functools
import sys
import threading
from collections import defaultdict, Counter

from django.apps.config import AppConfig
from django.core.exceptions import ImproperlyConfigured, AppRegistryNotReady


class Apps:
    """
    注册settings INSTALLED_APPS的应用
    """

    def __init__(self, installed_apps=()):

        if installed_apps is None and hasattr(sys.modules[__name__], "apps"):
            raise RuntimeError("You must supply an installed_apps argument.")

        # Mapping of app labels => model names => model classes. Every time a
        # model is imported, ModelBase.__new__ calls apps.register_model which
        # creates an entry in all_models. All imported models are registered,
        # regardless of whether they're defined in an installed application
        # and whether the registry has been populated. Since it isn't possible
        # to reimport a module safely (it could reexecute initialization code)
        # all_models is never overridden or reset.
        self.all_models = defaultdict(dict)

        # 将app标签映射到已配置INSTALLED_APPS的应用实例
        self.app_configs = {}

        # 应用配置的堆栈, 用set_available_apps和set_installed_apps保存当前状态
        self.stored_app_configs = []

        # 判断应用是否已注册
        self.apps_ready = self.models_ready = self.ready = False

        # 专为自动加载
        self.ready_event = threading.Event()

        # 为线程安全上锁
        self._lock = threading.RLock()
        self.loading = False

        # Maps ("app_label", "modelname") tuples to lists of functions to be
        # called when the corresponding model is ready. Used by this class's
        # `lazy_model_operation()` and `do_pending_operations()` methods.
        self._pending_operations = defaultdict(list)

        if installed_apps is not None:
            self.populate(installed_apps)

    def populate(self, installed_apps=None):
        """
        加载配置和模型

        导入每个应用模块以及相应的模型
        这是线程安全且幂等的, 但不可重入
        """
        if self.ready:
            return

        # 在初始化WSGI可调用函数之前, 在创建线程的服务器上, 可能会有两个线程并行执行populate()
        # 所以需要上锁
        with self._lock:
            if self.ready:
                return

            # 上锁阻止其他进行执行, 以下的操作都具有原子性
            if self.loading:
                # 阻止重复调用, 避免AppConfig.ready()调用两次
                raise RuntimeError("populate() isn`t reentrant")
            self.loading = True

            # 阶段1: 初始化应用程序配置并导入应用程序模块
            for entry in installed_apps:
                if isinstance(entry, AppConfig):
                    app_config = entry
                else:
                    app_config = AppConfig.create(entry)
                if app_config.label in self.app_configs:
                    raise ImproperlyConfigured(
                        "Application labels aren't unique, "
                        "duplicates: %s" % app_config.label
                    )

                self.app_configs[app_config.label] = app_config
                app_config.apps = self

            # 检查重复的app names
            counts = Counter(
                app_config.name for app_config in self.app_configs.values()
            )
            duplicates = [name for name, count in counts.most_common() if count > 1]
            if duplicates:
                raise ImproperlyConfigured(
                    "Application names aren't unique, "
                    "duplicates: %s" % ", ".join(duplicates)
                )

            self.apps_ready = True

            # 阶段2: 导入模型模块
            for app_config in self.app_configs.values():
                app_config.import_models()

            self.clear_cache()

            self.models_ready = True

            # 阶段3: 运行ready()
            for app_config in self.get_app_configs():
                app_config.ready()

            self.ready = True
            self.ready_event.set()

    # 对于django的测试套件来说, 这个方法是性能的关键
    @functools.lru_cache(maxsize=None)
    def get_models(self, include_auto_created=False, include_sapped=False):
        """
        返回所有在INSTALLED_APPS里面的模型列表

        - 自动为多对多关系创建模型, 不需要显式的创建中间表
        - 被替换的模型

        """
        self.check_models_ready()

    def get_app_configs(self):
        """导入应用并返回app配置迭代器"""
        self.check_apps_ready()
        return self.app_configs.values()

    def check_apps_ready(self):
        """如果所有的模型还没有被导入就报错"""
        if not self.apps_ready:
            from django.conf import settings

            settings.INSTALLED_APPS
            raise AppRegistryNotReady("Apps aren't loaded yet.")

    def check_models_ready(self):
        if not self.apps_ready:
            from django.conf import settings

            settings.INSTALLED_APPS
            raise AppRegistryNotReady("Apps aren't loaded yet.")

    def clear_cache(self):
        """
        清除所有的内部缓存, 修改app注册的时候使用
        经常在test中使用
        """
        # 调用每个模型的过期缓存. 会清除所有的关系树和字段缓存
        self.get_models.cache_clear()


apps = Apps(installed_apps=None)