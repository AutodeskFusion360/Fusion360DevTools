import adsk.core

from ... import config
from ...lib import fusion360utils as futil

app = adsk.core.Application.get()
ui = app.userInterface

CMD_IDS = ['ScriptsManagerCommand', 'ExchangeAppStoreCommand']
IS_PROMOTED = True

WORKSPACE_ID = config.design_workspace
TAB_ID = config.design_tab_id
TAB_NAME = config.design_tab_name

PANEL_ID = config.addins_panel_id
PANEL_NAME = config.addins_panel_name
PANEL_AFTER = config.addins_panel_after

local_handlers = []


def start():
    global IS_PROMOTED
    workspace = ui.workspaces.itemById(WORKSPACE_ID)

    toolbar_tab = workspace.toolbarTabs.itemById(TAB_ID)
    if toolbar_tab is None:
        toolbar_tab = workspace.toolbarTabs.add(TAB_ID, TAB_NAME)

    panel = toolbar_tab.toolbarPanels.itemById(PANEL_ID)
    if panel is None:
        panel = toolbar_tab.toolbarPanels.add(PANEL_ID, PANEL_NAME, PANEL_AFTER, False)

    for cmd_id in CMD_IDS:
        cmd_def = ui.commandDefinitions.itemById(cmd_id)
        control = panel.controls.addCommand(cmd_def)
        control.isPromoted = IS_PROMOTED
        IS_PROMOTED = False


def stop():
    workspace = ui.workspaces.itemById(WORKSPACE_ID)
    panel = workspace.toolbarPanels.itemById(PANEL_ID)
    toolbar_tab = workspace.toolbarTabs.itemById(TAB_ID)

    for cmd_id in CMD_IDS:
        command_control = panel.controls.itemById(cmd_id)

        if command_control:
            command_control.deleteMe()
        if panel.controls.count == 0:
            panel.deleteMe()
        if toolbar_tab.toolbarPanels.count == 0:
            toolbar_tab.deleteMe()
