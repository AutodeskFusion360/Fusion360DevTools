from .apiExplorer import entry as api_explorer
from .attributes import add, all, selected
from .data import entry as data
from .existing import entry as existing
from .uiExplorer import entry as ui_explorer

commands = [
    add, all, selected,
    data,
    api_explorer,
    ui_explorer,
    existing
]


def start():
    for command in commands:
        command.start()


def stop():
    for command in commands:
        command.stop()
