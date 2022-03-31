#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @FileName :__init__.py.py
# @Author   :Lowell
# @Time     :2022/3/30 08:59
import importlib
import os
import time
import warnings
from pathlib import Path

from django.conf import global_settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.deprecation import RemovedInDjango50Warning
from django.utils.functional import LazyObject, empty

ENVIRONMENT_VARIABLE = "DJANGO_SETTINGS_MODULE"

USE_DEPRECATED_PYTZ_DEPRECATED_MSG = (
    "The USE_DEPRECATED_PYTZ setting, and support for pytz timezones is "
    "deprecated in favor of the stdlib zoneinfo module. Please update your "
    "code to use zoneinfo and remove the USE_DEPRECATED_PYTZ setting."
)

USE_L10N_DEPRECATED_MSG = (
    "The USE_L10N setting is deprecated. Starting with Django 5.0, localized "
    "formatting of data will always be enabled. For example Django will "
    "display numbers and dates using the format of the current locale."
)

# CSRF Cookie会在django5.0版本移除
CSRF_COOKIE_MASKED_DEPRECATED_MSG = (
    "The CSRF_COOKIE_MASKED transitional setting is deprecated. Support for "
    "it will be removed in Django 5.0."
)


class LazySettings(LazyObject):
    """
    Django使用DJANGO_SETTINGS_MODULE所指向的模块
    """

    def _setup(self, name=None):
        """
        根据环境变量DJANGO_SETTINGS_MODULE加载settings模块
        """
        settings_module = os.environ.get(ENVIRONMENT_VARIABLE)
        if not settings_module:
            desc = ("setting %s" % name) if name else "settings"
            raise ImproperlyConfigured(
                "Requested %s, but settings are not configured. "
                "You must either define the environment variable %s "
                "or call settings.configure() before accessing settings."
                % (desc, ENVIRONMENT_VARIABLE)
            )

        self._wrapped = Settings(settings_module)

    def __repr__(self):
        if self._wrapped is empty:
            return "<LazySettings [Unevaluated]>"
        return '<LazySettings "%(settings_module)s">' % {
            "settings_module": self._wrapped.SETTINGS_MODULE,
        }

    def __getattr__(self, name):
        """返回setting里的值, 并缓存到self.__dict__中"""
        if (_wrapped := self._wrapped) is empty:
            self._setup()
            _wrapped = self._wrapped
        val = getattr(_wrapped, name)

        # 出于性能原因, 在此处执行此操作, 以便缓存修改后的值
        if name in {"MEDIA_URL", "STATIC_URL"} and val is not None:
            val = self._add_script_prefix(val)
        elif name == "SECRET_KEY" and not val:
            raise ImproperlyConfigured("The SECRET_KEY setting must not be empty.")

        self.__dict__[name] = val
        return val

    def __setattr__(self, name, value):
        """
        更新所有的setting配置, 或者更新单个配置变量
        """
        if name == "_wrapped":
            self.__dict__.clear()
        else:
            self.__dict__.pop(name, None)
        super().__setattr__(name, value)

    def __delattr__(self, name):
        """删除某个配置"""
        super().__delattr__(name)
        self.__dict__.pop(name, None)

    @property
    def configured(self):
        """判断如果settings已经配置过了"""
        return self._wrapped is not empty

    @staticmethod
    def _add_script_prefix(value):
        """
        将脚本名称前缀加到相对路径
        """
        # 不要把前缀加到绝对路径
        if value.startswith(("http://", "https://", "/")):
            return value
        from django.urls import get_script_prefix

        return "%s%s" % (get_script_prefix(), value)


class Settings:
    def __init__(self, settings_module):
        # 加载全局settings规则
        for setting in dir(global_settings):
            if setting.isupper():
                # 加载所有全大写的变量
                setattr(self, setting, getattr(global_settings, setting))

        self.SETTINGS_MODULE = settings_module

        mod = importlib.import_module(self.SETTINGS_MODULE)

        tuple_settings = (
            "ALLOWED_HOSTS",
            "INSTALLED_APPS",
            "TEMPLATE_DIRS",
            "LOCALE_PATHS",
            "SECRET_KEY_FALLBACKS",
        )
        self._explicit_settings = set()
        # 加载用户自定义的settings配置
        for setting in dir(mod):
            if setting.isupper():
                setting_value = getattr(mod, setting)

                if setting in tuple_settings and not isinstance(
                        setting_value, (list, tuple)
                ):
                    raise ImproperlyConfigured(
                        "The %s setting must be a list or a tuple." % setting
                    )
                setattr(self, setting, setting_value)
                self._explicit_settings.add(setting)

        if self.USE_TZ is False and not self.is_overridden("USE_TZ"):
            warnings.warn(
                "The default value of USE_TZ will change from False to True "
                "in Django 5.0. Set USE_TZ to False in your project settings "
                "if you want to keep the current default behavior.",
                category=RemovedInDjango50Warning,
            )

        if self.is_overridden("USE_DEPRECATED_PYTZ"):
            warnings.warn(USE_DEPRECATED_PYTZ_DEPRECATED_MSG, RemovedInDjango50Warning)

        if self.is_overridden("CSRF_COOKIE_MASKED"):
            warnings.warn(CSRF_COOKIE_MASKED_DEPRECATED_MSG, RemovedInDjango50Warning)

        if hasattr(time, "tzset") and self.TIME_ZONE:
            # 如果可以就验证系统时区, 如果没有就不做任何处理
            zoneinfo_root = Path("usr/share/zoneinfo")
            zone_info_file = zoneinfo_root.joinpath(*self.TIME_ZONE.split("/"))
            if zoneinfo_root.exists() and not zone_info_file.exists():
                raise ValueError("Incorrect timezone setting: %s" % self.TIME_ZONE)
            # 将时区设置为环境变量 (#2315)
            os.environ["TZ"] = self.TIME_ZONE
            time.tzset()

        if self.is_overridden("USE_L10N"):
            warnings.warn(USE_L10N_DEPRECATED_MSG, RemovedInDjango50Warning)

    def is_overridden(self, setting):
        return setting in self._explicit_settings

    def __repr__(self):
        return '<%(cls)s "%(settings_module)s">' % {
            "cls": self.__class__.__name__,
            "settings_module": self.SETTINGS_MODULE,
        }


settings = LazySettings()