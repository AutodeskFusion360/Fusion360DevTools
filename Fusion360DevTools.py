# Author-Patrick Rainsberry
# Description-Collection of useful utilities to aid in the development of a Fusion 360 Add-in.

from . import commands
from .lib.fusion360utils import cmd_utils, general_utils


def run(context):
    try:
        commands.start()
    except:
        general_utils.handle_error('run')


def stop(context):
    try:
        cmd_utils.clear_handlers()
        commands.stop()

    except:
        general_utils.handle_error('stop')
