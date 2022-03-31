#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @FileName :__init__.py.py
# @Author   :Lowell
# @Time     :2022/3/29 19:18
import functools
import os
import pkgutil
import sys
from collections import defaultdict
from difflib import get_close_matches
from importlib import import_module

import django
from django.apps import apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import (
    CommandParser,
    handle_default_options,
    CommandError, BaseCommand
)
from django.core.management.color import color_style
from django.utils import autoreload


def find_commands(management_dir):
    """
    获取命令目录的路径, 返回所有可用命令的名称列表
    """
    command_dir = os.path.join(management_dir, "commands")
    return [
        name
        for _, name, is_pkg in pkgutil.iter_modules([command_dir])
        if not is_pkg and not name.startswith("_")
    ]


def load_command_class(app_name, name):
    """
    Given a command name and an application name, return the Command
    class instance. Allow all errors raised by the import process
    (ImportError, AttributeError) to propagate.
    """
    module = import_module("%s.management.commands.%s" % (app_name, name))
    return module.Command()


@functools.lru_cache(maxsize=None)
def get_commands():
    """
    返回所有命令, 包括django自带的默认命令,
    以及用户在INSTALLED_APPS注册的app目录中management文件夹中定义的命令
    """
    commands = {name: "django.core" for name in find_commands(__path__[0])}

    if not settings.configured:
        return commands

    for app_config in reversed(apps.get_app_configs()):
        path = os.path.join(app_config.path, "management")
        commands.update({name: app_config for name in find_commands(path)})

    return commands


class ManagementUtility:
    """
    封装了django-admin以及manage.py工具的逻辑
    """
    def __init__(self, argv=None):
        self.argv = argv or sys.argv[:]     # 获取命令参数
        self.prog_name = os.path.basename(self.argv[0])     # manage管理工具命令首个参数
        if self.prog_name == "__main__.py":
            self.prog_name = "python -m django"
        self.settings_exception = None

    def main_help_text(self, commands_only=False):
        """Return the script's main help text, as a string."""
        if commands_only:
            usage = sorted(get_commands())
        else:
            usage = [
                "",
                "Type '%s help <subcommand>' for help on a specific subcommand."
                % self.prog_name,
                "",
                "Available subcommands:",
            ]
            commands_dict = defaultdict(lambda: [])
            for name, app in get_commands().items():
                if app == "django.core":
                    app = "django"
                else:
                    app = app.rpartition(".")[-1]
                commands_dict[app].append(name)
            style = color_style()
            for app in sorted(commands_dict):
                usage.append("")
                usage.append(style.NOTICE("[%s]" % app))
                for name in sorted(commands_dict[app]):
                    usage.append("    %s" % name)
            # Output an extra note if settings are not properly configured
            if self.settings_exception is not None:
                usage.append(
                    style.NOTICE(
                        "Note that only Django core commands are listed "
                        "as settings are not properly configured (error: %s)."
                        % self.settings_exception
                    )
                )

        return "\n".join(usage)

    def autocomplete(self):
        ...

    def execute(self):
        """
        通过获取的命令行参数, 为该命令行参数创建适当的命令解析器, 然后执行该命令
        """
        try:
            subcommand = self.argv[1]
        except IndexError:
            subcommand = "help"     # 如果没有参数就默认为help

        parser = CommandParser(
            prog=self.prog_name,
            usage="%(prog)s subcommand [options] [args]",
            add_help=False,
            allow_abbrev=False
        )
        parser.add_argument("--settings")
        parser.add_argument("--pythonpath")
        parser.add_argument("args", nargs="*")  # 最后捕获全部参数
        try:
            options, args = parser.parse_known_args(self.argv[2:])
            handle_default_options(options)
        except CommandError:
            pass

        try:
            settings.INSTALLED_APPS
        except ImproperlyConfigured as exc:
            self.settings_exception = exc
        except ImportError as exc:
            self.settings_exception = exc

        if settings.configured:
            # 如果代码修改过, 就自动重启开发服务器
            if subcommand == "runserver" and "--noreload" not in self.argv:
                try:
                    autoreload.check_errors(django.setup)()
                except Exception:
                    # 这个异常将会在autoreloader启动的子进程中抛出
                    # 加载空的应用列表来假装异常没有发生
                    apps.all_models = defaultdict(dict)
                    apps.app_configs = {}
                    apps.apps_ready = apps.models_ready = apps.ready = True

                    _parser = self.fetch_command("runserver").create_parser(
                        "django", "runserver"
                    )
                    _options, _args = _parser.parse_known_args(self.argv[2:])
                    for _arg in _args:
                        self.argv.remove(_arg)

            else:
                django.setup()

        self.autocomplete()

        if subcommand == "help":
            if "--commands" in args:
                sys.stdout.write(self.main_help_text(commands_only=True) + "\n")
            elif not options.args:
                sys.stdout.write(self.main_help_text() + "\n")
            else:
                self.fetch_command(options.args[0]).print_help(
                    self.prog_name, options.args[0]
                )
        # Special-cases: We want 'django-admin --version' and
        # 'django-admin --help' to work, for backwards compatibility.
        elif subcommand == "version" or self.argv[1:] == ["--version"]:
            sys.stdout.write(django.get_version() + "\n")
        elif self.argv[1:] in (["--help"], ["-h"]):
            sys.stdout.write(self.main_help_text() + "\n")
        else:
            self.fetch_command(subcommand).run_from_argv(self.argv)

    def fetch_command(self, subcommand):
        """

        """
        commands = get_commands()
        try:
            app_name = commands[subcommand]
        except KeyError:
            if os.environ.get("DJANGO_SETTINGS_MODULE"):
                settings.INSTALLED_APPS
            elif not settings.configured:
                sys.stderr.write("No Django settings specified.\n")
            possible_matches = get_close_matches(subcommand, commands)
            sys.stderr.write("Unknown command: %r" % subcommand)
            if possible_matches:
                sys.stderr.write(". Did you mean %s?" % possible_matches[0])
            sys.stderr.write("\nType '%s help' for usage.\n" % self.prog_name)
            sys.exit(1)
        if isinstance(app_name, BaseCommand):
            # 如果已经加载了命令, 就直接使用
            klass = app_name
        else:
            klass = load_command_class(app_name, subcommand)
        return klass


def execute_from_command_line(argv=None):
    """
    manage.py管理工具
    """
    utility = ManagementUtility(argv)
    utility.execute()