#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @FileName :exceptions.py
# @Author   :Lowell
# @Time     :2022/3/30 09:55


class ImproperlyConfigured(Exception):
    """Django 配置不正确"""
    pass


class AppRegistryNotReady(Exception):
    """django.apps注册失败"""
    pass

