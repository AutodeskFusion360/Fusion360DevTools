from .apiExplorer import entry as api_explorer
from .appearances import entry as appearance
from .attributes import add, all, selected
from .test import start, stop, run, performanceStart, performanceStop
from .data import entry as data
from .existing import entry as existing
from .uiExplorer import entry as ui_explorer

commands = [
    add, all, selected,
    data,
    api_explorer,
    ui_explorer,
    existing,
    appearance,
    start, stop, run, performanceStart, performanceStop
]


def start():
    for command in commands:
        command.start()


def stop():
    for command in commands:
        command.stop()
