import os
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from importlib import import_module

config_path = Path("config.toml")
if not config_path.exists():
    config = None
else:
    with config_path.open(mode="rb") as f:
        config = tomllib.load(f)
    PREFIX = config['bot']['PREFIX']

HELP_COMMANDS = {}

async def init_help(list_all_plugins):
    for plugin in list_all_plugins:
        imported_plugin = import_module("mahiru.plugins." + plugin)
        if hasattr(imported_plugin, "__PLUGIN__") and imported_plugin.__PLUGIN__:
            if not imported_plugin.__PLUGIN__.lower() in HELP_COMMANDS:
                HELP_COMMANDS[imported_plugin.__PLUGIN__.lower()] = imported_plugin
            else:
                raise Exception("Can't have two plugin with the same name! Please change one")
        if hasattr(imported_plugin, "__HELP__") and imported_plugin.__HELP__:
            HELP_COMMANDS[imported_plugin.__PLUGIN__.lower()] = imported_plugin
