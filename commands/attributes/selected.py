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
    # Create a command Definition.
    cmd_def = ui.commandDefinitions.itemById(CMD_ID)
    if cmd_def:
        cmd_def.deleteMe()
    cmd_def = ui.commandDefinitions.addButtonDefinition(CMD_ID, CMD_NAME, CMD_Description, ICON_FOLDER)
    futil.add_handler(cmd_def.commandCreated, command_created)

    # Create the button command control in the UI
    workspace = ui.workspaces.itemById(WORKSPACE_ID)

    toolbar_tab = workspace.toolbarTabs.itemById(TAB_ID)
    if toolbar_tab is None:
        toolbar_tab = workspace.toolbarTabs.add(TAB_ID, TAB_NAME)

    panel = toolbar_tab.toolbarPanels.itemById(PANEL_ID)
    if panel is None:
        panel = toolbar_tab.toolbarPanels.add(PANEL_ID, PANEL_NAME, PANEL_AFTER, False)

    control = panel.controls.addCommand(cmd_def, COMMAND_BESIDE_ID, False)
    control.isPromoted = IS_PROMOTED


# Executed when add-in is stopped.
def stop():
    workspace = ui.workspaces.itemById(WORKSPACE_ID)
    panel = workspace.toolbarPanels.itemById(PANEL_ID)
    toolbar_tab = workspace.toolbarTabs.itemById(TAB_ID)
    command_control = panel.controls.itemById(CMD_ID)
    command_definition = ui.commandDefinitions.itemById(CMD_ID)

    if command_control:
        command_control.deleteMe()
    if command_definition:
        command_definition.deleteMe()
    if not len(panel.controls):
        panel.deleteMe()
    if not len(toolbar_tab.toolbarPanels):
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

