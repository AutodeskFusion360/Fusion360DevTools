#  Copyright 2022 by Autodesk, Inc.
#  Permission to use, copy, modify, and distribute this software in object code form
#  for any purpose and without fee is hereby granted, provided that the above copyright
#  notice appears in all copies and that both that copyright notice and the limited
#  warranty and restricted rights notice below appear in all supporting documentation.
#
#  AUTODESK PROVIDES THIS PROGRAM "AS IS" AND WITH ALL FAULTS. AUTODESK SPECIFICALLY
#  DISCLAIMS ANY IMPLIED WARRANTY OF MERCHANTABILITY OR FITNESS FOR A PARTICULAR USE.
#  AUTODESK, INC. DOES NOT WARRANT THAT THE OPERATION OF THE PROGRAM WILL BE
#  UNINTERRUPTED OR ERROR FREE.

import cProfile
import sys

import adsk.core

from ... import config
from ...lib import fusion360utils as futil

app = adsk.core.Application.get()
ui = app.userInterface

# Since Python 3.12 cProfile attaches itself to the sys.monitoring profiler slot instead of
# sys.setprofile.  Only one profiler can own that slot, it is not released when the profiler
# object is garbage collected, and enabling a second one raises a ValueError.  A capture that
# is never stopped would otherwise block every later capture for the rest of the session.
_MONITORING = getattr(sys, 'monitoring', None)


def release_profiler():
    """Disables the current profiler, if any, and frees the profiler slot."""
    profiler = config.PROFILER
    config.PROFILER = None

    if profiler is not None:
        profiler.disable()

    # Recover the slot from a profiler we no longer hold a reference to.
    if _MONITORING is not None and _MONITORING.get_tool(_MONITORING.PROFILER_ID) == 'cProfile':
        futil.log('Releasing an abandoned cProfile profiler')
        _MONITORING.set_events(_MONITORING.PROFILER_ID, 0)
        _MONITORING.free_tool_id(_MONITORING.PROFILER_ID)


def start_profiler():
    """Starts a new profile capture, replacing any capture already in progress."""
    release_profiler()

    if _MONITORING is not None:
        owner = _MONITORING.get_tool(_MONITORING.PROFILER_ID)
        if owner is not None:
            raise RuntimeError(f"Python profiling is already in use by '{owner}' "
                               f"so a performance capture can't be started.")

    config.PROFILER = cProfile.Profile()
    config.PROFILER.enable()


def show_text_palette():
    """Makes the TEXT COMMANDS palette visible, this is where log output is written."""
    text_palette = ui.palettes.itemById('TextCommands')
    if text_palette is not None and not text_palette.isVisible:
        text_palette.isVisible = True
