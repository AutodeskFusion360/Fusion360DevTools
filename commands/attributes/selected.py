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

import adsk.core
import os
from ...lib import fusion360utils as futil
from ... import config
from . import attributes_utils as au

app = adsk.core.Application.get()
ui = app.userInterface

CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_attributes_selected'
CMD_NAME = 'Attributes - Selected'
CMD_Description = 'View attributes for selection, for testing'
IS_PROMOTED = False
COMMAND_BESIDE_ID = ''

WORKSPACE_ID = config.design_workspace
TAB_ID = config.design_tab_id
TAB_NAME = config.design_tab_name

PANEL_ID = config.attributes_panel_id
PANEL_NAME = config.attributes_panel_name
PANEL_AFTER = config.attributes_panel_after

ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', 'selected', '')

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
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


def command_created(args: adsk.core.CommandCreatedEventArgs):
    futil.add_handler(args.command.inputChanged, command_input_changed, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)
    inputs = args.command.commandInputs
    args.command.isOKButtonVisible = False

    selection_input = inputs.addSelectionInput('selection_input', 'Selection', 'Select Something')
    selection_input.setSelectionLimits(0, 1)

    inputs.addBoolValueInput('filter_by_group', 'Filter by Group Name?', True)
    inputs.addStringValueInput('attribute_group', 'Attribute Group', '')

    title = inputs.addTextBoxCommandInput('title', 'Details:', 'Attributes for current selection', 1, True)
    title.isFullWidth = True
    feedback = inputs.addTextBoxCommandInput('feedback', 'Details:', 'Nothing Selected', 1, True)
    feedback.isFullWidth = True


def command_input_changed(args: adsk.core.InputChangedEventArgs):
    inputs = args.inputs
    selection_input: adsk.core.SelectionCommandInput = inputs.itemById('selection_input')
    filter_by_group: adsk.core.BoolValueCommandInput = inputs.itemById('filter_by_group')
    attribute_group: adsk.core.StringValueCommandInput = inputs.itemById('attribute_group')
    feedback: adsk.core.TextBoxCommandInput = inputs.itemById('feedback')

    if selection_input.selectionCount > 0:
        selection = selection_input.selection(0).entity
        msg_list = au.attributes_for_selection(selection, filter_by_group.value, attribute_group.value)
        au.update_feedback_from_list(feedback, msg_list)


def command_destroy(args: adsk.core.CommandEventArgs):
    global local_handlers
    local_handlers = []

