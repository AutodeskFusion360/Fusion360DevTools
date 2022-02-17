from .addins import existing, folder
from .apiExplorer import entry as api_explorer
from .appearances import entry as appearance
from .attributes import add, all, selected
from .closeAll import entry as close_all
from .commandStream import entry as command_stream
from .data import entry as data
from .help import api, chm, github
from .test import record, stop, run, performanceStart, performanceStop
from .uiExplorer import entry as ui_explorer
from .. import config

commands = [
    add, all, selected,
    data,
    close_all,
    api_explorer,
    ui_explorer,
    existing, folder,
    appearance,
    performanceStart, performanceStop,
    api, chm, github,
    command_stream
]

if config.ENABLE_RECORD_COMMANDS:
    commands.append(record)
    commands.append(stop)
    commands.append(run)


def start():
    for command in commands:
        command.start()


def stop():
    for command in commands:
        command.stop()
