#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @FileName :functional.py
# @Author   :Lowell
# @Time     :2022/3/30 09:00
import copy
import operator

empty = object()


def new_method_proxy(func):
    def inner(self, *args):
        if (_wrapped := self._wrapped) is empty:
            self._setup()
            _wrapped = self._wrapped
        return func(_wrapped, *args)

    inner._mask_wrapped = False
    return inner


class LazyObject:
    """
    延迟对象实例化基类

    通过子类可以修改实例化操作, 如果不需要, 就使用SimpleLazyObject
    """

    # 避免__init__无限递归 (#19456)
    _wrapped = None

    def __init__(self):
        # 如果子类重写了__init__方法
        # 那么可能同样需要重写__copy__和__deepcopy__方法
        self._wrapped = empty

    def __getattribute__(self, name):
        if name == "_wrapped":
            # 避免获取wrapped对象的时候递归
            return super().__getattribute__(name)
        value = super().__getattribute__(name)
        # 也有可能使用__getattr__
        if not getattr(value, "_mask_wrapped", True):
            raise AttributeError
        return value

    __getattr__ = new_method_proxy(getattr)

    def __setattr__(self, name, value):
        if name == "_wrapped":
            # 调整到__dict__, 避免__setattr__循环
            self.__dict__["_wrapped"] = value
        else:
            if self._wrapped is empty:
                self._setup()
            setattr(self._wrapped, name, value)

    def __delattr__(self, name):
        if name == "_wrapped":
            raise TypeError("can`t delete _wrapped.")
        if self._wrapped is empty:
            self._setup()
        delattr(self._wrapped, name)

    def _setup(self):
        """
        必须在子类中实现_setup方法, 以初始化wrapped对象
        """
        raise NotImplementedError(
            "subclasses of LazyObject must provide a _setup() method"
        )

    def __reduce__(self):
        if self._wrapped is empty:
            self._setup()
        return (unpickle_lazyobject, (self._wrapped,))

    def __copy__(self):
        if self._wrapped is empty:
            # 如果没有进行初始化, 就复制wrapper包装者. 使用type(self),
            # 而不是self.__class__, 因为这是被代理的, 隔绝依赖
            return type(self)()
        else:
            # 如果初始化了, 就返回被包装对象的复制版本
            return copy.copy(self._wrapped)

    def __deepcopy__(self, memo):
        if self._wrapped is empty:
            # 必须使用type(self),
            # 而不是self.__class__, 因为这是被代理的, 隔绝依赖
            result = type(self)()
            memo[id(self)] = result
            return result
        return copy.deepcopy(self._wrapped, memo)

    __bytes__ = new_method_proxy(bytes)
    __str__ = new_method_proxy(str)
    __bool__ = new_method_proxy(bool)

    __dir__ = new_method_proxy(dir)

    __class__ = property(new_method_proxy(operator.attrgetter("__class__")))
    __eq__ = new_method_proxy(operator.eq)
    __lt__ = new_method_proxy(operator.lt)
    __gt__ = new_method_proxy(operator.gt)
    __ne__ = new_method_proxy(operator.ne)
    __hash__ = new_method_proxy(hash)

    # 支持列表/元组/字典
    __getitem__ = new_method_proxy(operator.getitem)
    __setitem__ = new_method_proxy(operator.setitem)
    __delitem__ = new_method_proxy(operator.delitem)
    __iter__ = new_method_proxy(iter)
    __len__ = new_method_proxy(len)
    __contains__ = new_method_proxy(operator.contains)


def unpickle_lazyobject(wrapped):
    """
    用于反序列化懒加载对象, 只需要返回被包装的对象
    """
    return wrapped