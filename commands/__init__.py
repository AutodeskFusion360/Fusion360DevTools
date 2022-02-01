from .apiExplorer import entry as api_explorer
from .appearances import entry as appearance
from .attributes import add, all, selected
from .test import record, stop, run, performanceStart, performanceStop
from .data import entry as data
from .existing import entry as existing
from .uiExplorer import entry as ui_explorer
from .help import api, chm

commands = [
    add, all, selected,
    data,
    api_explorer,
    ui_explorer,
    existing,
    appearance,
    record, stop, run, performanceStart, performanceStop,
    api, chm
]


def start():
    for command in commands:
        command.start()


def stop():
    for command in commands:
        command.stop()
