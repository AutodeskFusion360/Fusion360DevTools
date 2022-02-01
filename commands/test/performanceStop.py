import adsk.core
import adsk.fusion
import os
from ...lib import fusion360utils as futil
from ... import config
from .testUtils import start_recording

import cProfile
import pstats
import io
from pstats import SortKey

app = adsk.core.Application.get()
ui = app.userInterface

CMD_NAME = 'Stop Performance Capture'
CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_{CMD_NAME}'
CMD_Description = 'Stop recording performance information and display results'
IS_PROMOTED = True

# Global variables by referencing values from /config.py
WORKSPACE_ID = config.design_workspace
TAB_ID = config.design_tab_id
TAB_NAME = config.design_tab_name

PANEL_ID = config.test_panel_id
PANEL_NAME = config.test_panel_name
PANEL_AFTER = config.test_panel_after

# Resource location for command icons, here we assume a sub folder in this directory named "resources".
ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', 'performanceStop', '')

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
    # Get the various UI elements for this command
    workspace = ui.workspaces.itemById(WORKSPACE_ID)
    panel = workspace.toolbarPanels.itemById(PANEL_ID)
    toolbar_tab = workspace.toolbarTabs.itemById(TAB_ID)
    control = panel.controls.itemById(CMD_ID)
    command_definition = ui.commandDefinitions.itemById(CMD_ID)

    # Delete the button command control
    if control:
        control.deleteMe()

    # Delete the command definition
    if command_definition:
        command_definition.deleteMe()

    # Delete the panel if it is empty
    if not len(panel.controls):
        panel.deleteMe()

    # Delete the tab if it is empty
    if not len(toolbar_tab.toolbarPanels):
        toolbar_tab.deleteMe()


# Function to be called when a user clicks the corresponding button in the UI.
def command_created(args: adsk.core.CommandCreatedEventArgs):
    futil.log(f'************Stop capturing performance profile information************')

    if config.PROFILER is None:
        ui.messageBox('You need to start capturing performance before you can stop.')
        return

    config.PROFILER.disable()
    inputs = args.command.commandInputs

    drop_down = inputs.addDropDownCommandInput('sort_key', 'Sort By', adsk.core.DropDownStyles.TextListDropDownStyle)
    drop_down.listItems.add('CUMULATIVE', True)
    drop_down.listItems.add('TIME', False)
    drop_down.listItems.add('NAME', False)
    drop_down.listItems.add('CALLS', False)
    drop_down.listItems.add('NFL', False)
    drop_down.listItems.add('FILENAME', False)

    inputs.addIntegerSpinnerCommandInput('num_lines', 'Number of Lines', 0, 1000, 5, 20)
    inputs.addBoolValueInput('strip_dirs', 'Remove directory names?', True, '', True)
    inputs.addTextBoxCommandInput('test_name', 'Test Name', 'My Test', 1, False)

    # Connect to the events that are needed by this command.
    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)
    futil.add_handler(args.command.inputChanged, command_input_changed, local_handlers=local_handlers)

    print_performance_results(inputs)


# This function will be called when the user clicks the OK button in the command dialog.
def command_execute(args: adsk.core.CommandEventArgs):
    inputs = args.command.commandInputs


def command_input_changed(args: adsk.core.InputChangedEventArgs):
    inputs = args.inputs
    print_performance_results(inputs)


# This function will be called when the user completes the command.
def command_destroy(args: adsk.core.CommandEventArgs):
    global local_handlers
    local_handlers = []


def print_performance_results(inputs: adsk.core.CommandInputs):
    futil.log(f'\n*************Performance Profile Results************\n')

    strip_dirs_input: adsk.core.BoolValueCommandInput = inputs.itemById('strip_dirs')
    sort_key_input: adsk.core.DropDownCommandInput = inputs.itemById('sort_key')
    num_lines_input: adsk.core.IntegerSpinnerCommandInput = inputs.itemById('num_lines')
    sort_key_selected_name = sort_key_input.selectedItem.name
    if sort_key_selected_name == 'CUMULATIVE':
        sort_by = SortKey.CUMULATIVE
    elif sort_key_selected_name == 'TIME':
        sort_by = SortKey.TIME
    elif sort_key_selected_name == 'NAME':
        sort_by = SortKey.NAME
    elif sort_key_selected_name == 'CALLS':
        sort_by = SortKey.CALLS
    elif sort_key_selected_name == 'NFL':
        sort_by = SortKey.NFL
    elif sort_key_selected_name == 'FILENAME':
        sort_by = SortKey.FILENAME
    else:
        sort_by = SortKey.CUMULATIVE

    # TODO add save to file
    s = io.StringIO()
    p_stats = pstats.Stats(config.PROFILER, stream=s)

    if strip_dirs_input.value:
        p_stats.strip_dirs()

    p_stats.sort_stats(sort_by)
    if num_lines_input.value > 0:
        p_stats.print_stats(num_lines_input.value)
    else:
        p_stats.print_stats()

    textPalette = ui.palettes.itemById('TextCommands')
    if not textPalette.isVisible:
        textPalette.isVisible = True

    futil.log(s.getvalue())
