import json

import adsk.core
import os
from ...lib import fusion360utils as futil
from ... import config
from .object_explorer import get_object_tree, get_new_tree, initialize_stack, set_selection, get_end_title, go_back

app = adsk.core.Application.get()
ui = app.userInterface

CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_explorer'
CMD_NAME = 'API Object Explorer'
CMD_Description = 'Explorer details of the API Object Model'
IS_PROMOTED = True
COMMAND_BESIDE_ID = ''

WORKSPACE_ID = config.design_workspace
TAB_ID = config.design_tab_id
TAB_NAME = config.design_tab_name

PANEL_ID = config.dev_panel_id
PANEL_NAME = config.dev_panel_name
PANEL_AFTER = config.dev_panel_after

PALETTE_NAME = config.api_palette_name
PALETTE_ID = config.ui_palette_id
PALETTE_URL = './commands/apiExplorer/resources/html/index.html'

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
    palette = ui.palettes.itemById(PALETTE_ID)

    if command_control:
        command_control.deleteMe()
    if command_definition:
        command_definition.deleteMe()
    if not len(panel.controls):
        panel.deleteMe()
    if not len(toolbar_tab.toolbarPanels):
        toolbar_tab.deleteMe()
    if palette:
        palette.deleteMe()


def command_created(args: adsk.core.CommandCreatedEventArgs):
    futil.add_handler(args.command.inputChanged, command_input_changed, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)
    futil.add_handler(args.command.incomingFromHTML, palette_incoming)

    inputs = args.command.commandInputs
    args.command.isOKButtonVisible = False

    initialize_stack()

    select_input = inputs.addSelectionInput('object_selection', 'Pick a Component', 'Get Component PIM info')
    select_input.setSelectionLimits(1, 1)

    browser_input = inputs.addBrowserCommandInput('component_palette', 'Component Details', PALETTE_URL, 400, 0)
    browser_input.isFullWidth = True


def command_input_changed(args: adsk.core.InputChangedEventArgs):
    changed_input = args.input
    inputs = args.inputs
    browser_input: adsk.core.BrowserCommandInput = inputs.itemById('component_palette')
    object_selection: adsk.core.SelectionCommandInput = inputs.itemById('object_selection')
    send_data = {'core': [{
        'id': 'empty_node',
        'text': 'Pick a Component Text',
    }]}

    if changed_input.id in ["object_selection", "filter_check"]:
        if object_selection.selectionCount > 0:
            entity = object_selection.selection(0).entity
            set_selection(entity)
            send_data = get_object_tree(entity)
            action = 'tree_refresh'
        else:
            action = 'tree_clear'
            initialize_stack()

        browser_input.sendInfoToHTML(action, json.dumps(send_data))


def palette_incoming(html_args: adsk.core.HTMLEventArgs):
    browser_input = html_args.browserCommandInput
    if not browser_input:
        return

    message_data: dict = json.loads(html_args.data)
    message_action = html_args.action

    if message_action == 'go_back':
        ui_tree = go_back()
        message_json = json.dumps(ui_tree)
        message_action = 'tree_refresh'
        browser_input.sendInfoToHTML(message_action, message_json)

    elif message_action == 'pick_node':
        if message_data['clickable']:
            obj_tree = get_new_tree(message_data['param_name'])
            message_action = 'tree_refresh'
        else:
            obj_tree = get_end_title(message_data['param_name'])
            message_action = 'title_refresh'

        message_json = json.dumps(obj_tree)
        browser_input.sendInfoToHTML(message_action, message_json)


def command_destroy(args: adsk.core.CommandEventArgs):
    global local_handlers
    local_handlers = []
