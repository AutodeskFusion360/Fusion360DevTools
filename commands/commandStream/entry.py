import adsk.core
import os
import json
from ...lib import fusion360utils as futil
from ... import config

app = adsk.core.Application.get()
ui = app.userInterface


CMD_NAME = 'Command Stream'
CMD_Description = 'Get information about commands being executed'

CMD_ID = f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_{CMD_NAME}'

IS_PROMOTED = True
COMMAND_BESIDE_ID = ''

WORKSPACE_ID = config.design_workspace
TAB_ID = config.design_tab_id
TAB_NAME = config.design_tab_name

PANEL_ID = config.info_panel_id
PANEL_NAME = config.info_panel_name
PANEL_AFTER = config.info_panel_after

PALETTE_NAME = config.command_stream_palette_name
PALETTE_ID = config.command_stream_palette_id
PALETTE_URL = './commands/commandStream/resources/html/index.html'
PALETTE_DOCKING = adsk.core.PaletteDockingStates.PaletteDockStateRight

ICON_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', '')

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
local_handlers = []

palette_handlers = []
COMMAND_HANDLER = None
SELECTION_HANDLER = None

LAST_COMMAND_ID = ''
SHOW_DUPLICATE_COMMANDS = False


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

    destroy_palette_and_events()


def command_created(args: adsk.core.CommandCreatedEventArgs):
    global COMMAND_HANDLER
    global SELECTION_HANDLER

    futil.add_handler(args.command.execute, command_execute, local_handlers=local_handlers)
    futil.add_handler(args.command.destroy, command_destroy, local_handlers=local_handlers)

    COMMAND_HANDLER = futil.add_handler(ui.commandStarting, command_starting, local_handlers=palette_handlers)
    SELECTION_HANDLER = futil.add_handler(ui.activeSelectionChanged, selection_changed, local_handlers=palette_handlers)


def command_execute(args: adsk.core.CommandEventArgs):
    palettes = ui.palettes
    palette = palettes.itemById(PALETTE_ID)
    if palette is None:
        palette = palettes.add(
            id=PALETTE_ID,
            name=PALETTE_NAME,
            htmlFileURL=PALETTE_URL,
            isVisible=True,
            showCloseButton=True,
            isResizable=True,
            width=650,
            height=600,
            useNewWebBrowser=True
        )
        futil.add_handler(palette.closed, palette_closed, local_handlers=palette_handlers)

    if palette.dockingState == adsk.core.PaletteDockingStates.PaletteDockStateFloating:
        palette.dockingState = PALETTE_DOCKING

    palette.isVisible = True


def command_destroy(args: adsk.core.CommandEventArgs):
    global local_handlers
    local_handlers = []


def palette_closed(args: adsk.core.UserInterfaceGeneralEventArgs):
    destroy_palette_and_events()


def destroy_palette_and_events():
    global palette_handlers
    global COMMAND_HANDLER
    global SELECTION_HANDLER
    palette_handlers = []

    palette = ui.palettes.itemById(PALETTE_ID)
    if palette:
        palette.deleteMe()

    if COMMAND_HANDLER is not None:
        ui.commandStarting.remove(COMMAND_HANDLER)
        COMMAND_HANDLER = None

    if SELECTION_HANDLER is not None:
        ui.activeSelectionChanged.remove(SELECTION_HANDLER)
        SELECTION_HANDLER = None


def palette_push(command, action_data):
    palette = ui.palettes.itemById(config.command_stream_palette_id)

    # Send message to the HTML Page
    if palette:
        palette.sendInfoToHTML(command, json.dumps(action_data))


def command_starting(args: adsk.core.ApplicationCommandEventArgs):
    global LAST_COMMAND_ID

    if (args.commandId == LAST_COMMAND_ID) and (not SHOW_DUPLICATE_COMMANDS):
        return

    LAST_COMMAND_ID = args.commandId
    command_definition = args.commandDefinition

    action_data = {
        'cmd_id': command_definition.id,
        'cmd_name': command_definition.name,
    }

    palette_push('command', action_data)


def selection_changed(args: adsk.core.ActiveSelectionEventArgs):
    selection_list = []
    for selection in args.currentSelection:
        selection_list.append(selection.entity.objectType)

    if len(selection_list) == 0:
        selection_list.append("Nothing Selected")

    action_data = {
        'selection_list': selection_list,
    }
    palette_push('selection', action_data)

