import os

import adsk.core

from .fusion_data import FusionData
from ... import config
from ...lib import fusion360utils as futil

app = adsk.core.Application.get()
ui = app.userInterface

CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_data_info'
CMD_NAME = 'Data Info'
CMD_Description = 'Use info about active document and Fusion Data'
IS_PROMOTED = True
COMMAND_BESIDE_ID = ''

WORKSPACE_ID = config.design_workspace
TAB_ID = config.design_tab_id
TAB_NAME = config.design_tab_name

PANEL_ID = config.data_panel_id
PANEL_NAME = config.data_panel_name
PANEL_AFTER = config.data_panel_after

ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', '')

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
local_handlers = []


# Executed when add-in is run.
def start():
    # Create a command Definition.
    cmd_def = ui.commandDefinitions.addButtonDefinition(CMD_ID, CMD_NAME, CMD_Description, ICON_FOLDER)
    futil.add_handler(cmd_def.commandCreated, command_created)

    # Create the button command control in the UI
    workspace = ui.workspaces.itemById(WORKSPACE_ID)
    panel = workspace.toolbarPanels.itemById(PANEL_ID)
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
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)
    inputs = args.command.commandInputs
    args.command.isOKButtonVisible = False

    success = False
    try:
        data_file = app.activeDocument.dataFile
        if data_file:
            data_info = FusionData(data_file=data_file)
            success = True
            text_boxes = []
            for key, value in data_info.str_dict().items():
                text_boxes.append(inputs.addTextBoxCommandInput(
                    f'data_info_box_{key}',
                    key.replace('_', ' '),
                    value, 1, False
                ))
            text_boxes[-1].isReadOnly = True
    except:
        futil.handle_error('data.info')

    if not success:
        data_failure_string = f'Error Getting Data Info\nMake sure active document has been saved'
        inputs.addTextBoxCommandInput('results_box', '', data_failure_string, 20, True)


def command_destroy(args: adsk.core.CommandEventArgs):
    global local_handlers
    local_handlers = []
