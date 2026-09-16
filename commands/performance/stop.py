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

import os

import adsk.core
import adsk.fusion

from . import palette
from . import report
from .profile_utils import release_profiler
from ... import config
from ...lib import fusion360utils as futil

app = adsk.core.Application.get()
ui = app.userInterface

CMD_NAME = 'Stop Performance Capture'
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_{CMD_NAME}'
CMD_Description = 'Stop recording performance information and show the results palette'
IS_PROMOTED = True

# Global variables by referencing values from /config.py
WORKSPACE_ID = config.design_workspace
TAB_ID = config.design_tab_id
TAB_NAME = config.design_tab_name

PANEL_ID = config.test_panel_id
PANEL_NAME = config.test_panel_name
PANEL_AFTER = config.test_panel_after

# Resource location for command icons, here we assume a sub folder in this directory named "resources".
ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', 'stop', '')

# Holds references to event handlers
local_handlers = []


# Executed when add-in is run.
def start():
    # ******************************** Create Command Definition ********************************
    cmd_def = ui.commandDefinitions.addButtonDefinition(CMD_ID, CMD_NAME, CMD_Description, ICON_FOLDER)

    # Add command created handler. The function passed here will be executed when the command is executed.
    futil.add_handler(cmd_def.commandCreated, command_created)

    # ******************************** Create Command Control ********************************
    # Get target workspace for the command.
    workspace = ui.workspaces.itemById(WORKSPACE_ID)

    # Get target toolbar tab for the command and create the tab if necessary.
    toolbar_tab = workspace.toolbarTabs.itemById(TAB_ID)
    if toolbar_tab is None:
        toolbar_tab = workspace.toolbarTabs.add(TAB_ID, TAB_NAME)

    # Get target panel for the command and and create the panel if necessary.
    panel = toolbar_tab.toolbarPanels.itemById(PANEL_ID)
    if panel is None:
        panel = toolbar_tab.toolbarPanels.add(PANEL_ID, PANEL_NAME, PANEL_AFTER, False)

    # Create the command control, i.e. a button in the UI.
    control = panel.controls.addCommand(cmd_def)

    # Now you can set various options on the control such as promoting it to always be shown.
    control.isPromoted = IS_PROMOTED


# Executed when add-in is stopped.
def stop():
    # A capture that is still running would keep the profiler slot for the whole session.
    release_profiler()
    palette.close()

    # Get the various UI elements for this command
    workspace = ui.workspaces.itemById(WORKSPACE_ID)
    panel = workspace.toolbarPanels.itemById(PANEL_ID)
    toolbar_tab = workspace.toolbarTabs.itemById(TAB_ID)
    command_control = panel.controls.itemById(CMD_ID)
    command_definition = ui.commandDefinitions.itemById(CMD_ID)

    # Delete the button command control
    if command_control:
        command_control.deleteMe()

    # Delete the command definition
    if command_definition:
        command_definition.deleteMe()

    # Delete the panel if it is empty
    if panel.controls.count == 0:
        panel.deleteMe()

    # Delete the tab if it is empty
    if toolbar_tab.toolbarPanels.count == 0:
        toolbar_tab.deleteMe()


# Function to be called when a user clicks the corresponding button in the UI.
def command_created(args: adsk.core.CommandCreatedEventArgs):
    futil.log(f'************Stop capturing performance profile information************')

    if config.PROFILER is None:
        ui.messageBox('You need to start capturing performance before you can stop.')
        args.command.isAutoExecute = False
        args.command.isOKButtonVisible = False
        return

    # Every option now lives in the results palette, so there is no dialog to fill in.
    args.command.isAutoExecute = True

    # Connect to the events that are needed by this command.
    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)


# This function will be called when the user clicks the OK button in the command dialog.
def command_execute(args: adsk.core.CommandEventArgs):
    try:
        capture = report.take_snapshot(config.PROFILER)
    except TypeError:
        # pstats raises a TypeError when the capture recorded no calls at all.
        release_profiler()
        futil.log('No performance profile information was captured.', force_console=True)
        ui.messageBox('No performance profile information was captured.\n\n'
                      'Start a capture, use the commands you want to measure, then stop it.')
        return

    # The capture is snapshotted, so the profiler itself is no longer needed and its
    # sys.monitoring slot should go back so the next capture can start.
    release_profiler()

    futil.log(f'{capture["label"]}: {capture["total_time"]:.3f} s, '
              f'{capture["total_calls"]} calls in {capture["function_count"]} functions',
              force_console=True)

    palette.show(capture)


# This function will be called when the user completes the command.
def command_destroy(args: adsk.core.CommandEventArgs):
    global local_handlers
    local_handlers = []
