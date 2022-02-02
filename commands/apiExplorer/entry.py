import json

import adsk.core
import os
from ...lib import fusion360utils as futil
from ... import config
from .object_explorer import get_object_tree, get_new_tree, initialize_stack, set_selection, get_end_title, go_back

app = adsk.core.Application.get()
ui = app.userInterface

CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_api_explorer'
CMD_NAME = 'API Object Explorer'
CMD_Description = 'Explorer details of the API Object Model'
IS_PROMOTED = True
COMMAND_BESIDE_ID = ''

WORKSPACE_ID = config.design_workspace
TAB_ID = config.design_tab_id
TAB_NAME = config.design_tab_name

PANEL_ID = config.info_panel_id
PANEL_NAME = config.info_panel_name
PANEL_AFTER = config.info_panel_after

PALETTE_NAME = config.api_palette_name
PALETTE_ID = config.api_palette_id
PALETTE_URL = './commands/apiExplorer/resources/html/index.html'

ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', '')

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

    message_action = html_args.action
    api_tree_data = {}
    response_action = ''

    if message_action == 'go_back':
        response_action = 'tree_refresh'
        api_tree_data = go_back()

    elif message_action == 'pick_node':
        message_data: dict = json.loads(html_args.data)
        if message_data['clickable']:
            api_tree_data = get_new_tree(message_data['param_name'])
            response_action = 'tree_refresh'
        else:
            api_tree_data = get_end_title(message_data['param_name'])
            response_action = 'title_refresh'

    response_data = json.dumps(api_tree_data)
    browser_input.sendInfoToHTML(response_action, response_data)


def command_destroy(args: adsk.core.CommandEventArgs):
    global local_handlers
    local_handlers = []
