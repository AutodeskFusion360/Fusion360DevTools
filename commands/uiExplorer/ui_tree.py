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

from typing import Union

import adsk.core
import adsk.fusion
from ...lib.fusion360utils import app, ui
from ...lib import fusion360utils as fus

types = {
    'Workspace': "workspace",
    'Toolbar Tab': "toolbar_tab",
    'Toolbar Panel': "panel",
    'Control': "control",
    'Command Definition': 'command',
    'Toolbar': 'toolbar'
}

NO_NAME_DROPDOWNS = []


def make_property(name, value):
    return {
        'text': f"<b>{name}</b>: {value}",
        'type': "property",
    }


def serialize_item(item: Union[adsk.core.Workspace, adsk.core.ToolbarTab,
                               adsk.core.ToolbarPanel, adsk.core.CommandDefinition], node_type):
    children = []
    item_name = node_type

    if hasattr(item, 'id'):
        children.append(make_property('id', item.id))
        item_name = item.id

    if hasattr(item, 'name'):
        children.append(make_property('name', item.name))
        item_name = item.name

    return {
        'text': f'{item_name} - {node_type}',
        'children': children,
        'type': types[node_type],
    }


def serialize_control(control: adsk.core.ToolbarControl):
    global NO_NAME_DROPDOWNS
    node_type = 'Control'

    children = [
        make_property('Control ID', control.id),
        make_property('Control Index', control.index),
        make_property('Object Type', control.objectType)
    ]
    if control.objectType == adsk.core.CommandControl.classType():
        control = adsk.core.CommandControl.cast(control)
        try:
            children.append(serialize_item(control.commandDefinition, 'Command Definition'))
            control_name = control.commandDefinition.name
        except RuntimeError:
            fus.handle_error(F'CommandControl has no CommandDefinition: {control.id}\n')
            control_name = control.id

    elif control.objectType == adsk.core.DropDownControl.classType():
        control = adsk.core.DropDownControl.cast(control)

        sub_control: adsk.core.ToolbarControl
        for sub_control in control.controls:
            sub_control_node = serialize_control(sub_control)
            children.append(sub_control_node)
        try:
            control_name = f'{control.name} - Dropdown'
        except RuntimeError:
            NO_NAME_DROPDOWNS.append(control.id)
            control_name = f'No Name - Dropdown {control.id}'

    elif control.objectType == adsk.core.SeparatorControl.classType():
        control_name = 'Separator'

    elif control.objectType == adsk.core.SplitButtonControl.classType():
        control = adsk.core.SplitButtonControl.cast(control)
        try:
            children.append({
                'text': f'Default Command Definition',
                'children': [serialize_item(control.defaultCommandDefinition, 'Command Definition')],
                'type': 'Command Definition',
            })
        except RuntimeError:
            fus.handle_error(F'SplitBox: Failed: to get Default Command Definition for: {control.id}\n')
            children.append({
                'text': f'Default Command Definition - Failed to get',
                'type': 'Command Definition',
            })
        try:
            if len(control.additionalDefinitions) > 0:
                sub_children = []
                for cmd_def in control.additionalDefinitions:
                    sub_children.append(serialize_item(cmd_def, 'Command Definition'))

                children.append({
                    'text': f'Additional Command Definitions',
                    'children': sub_children,
                    'type': 'Command Definition',
                })
        except RuntimeError:
            fus.handle_error(F'SplitBox: Failed: to get Additional Command Definitions for: {control.id}\n')
            children.append({
                'text': f'Additional Command Definitions - Failed to get',
                'type': 'Command Definition',
            })
        control_name = 'Split Button'

    else:
        control_name = control.objectType

    return {
        'text': f'{control_name} - {node_type}',
        'children': children,
        'type': types[node_type],
        'control_id': control.id,
        'control_name': control_name
    }


def get_ui_tree():
    root_nodes = []
    # FIXME WRONG!!!!!!!
    product: adsk.core.Product
    # for product in app.activeDocument.products:
    # for product in app.activeDocument.products:
    for workspace in ui.workspaces:
        fus.log(f'*********************| Workspace: {workspace.name} |*********************')
        workspace_node = serialize_item(workspace, 'Workspace')
        workspace_node['workspace_id'] = workspace.id
        workspace_node['workspace_name'] = workspace.name

        try:
            count = workspace.toolbarTabs.count
        except:
            count = False

        if count:
            for i in range(workspace.toolbarTabs.count):
                try:
                    tab = workspace.toolbarTabs.item(i)
                    tab_node = serialize_item(tab, 'Toolbar Tab')
                    # tab_node['workspace_id'] = workspace.id
                    # tab_node['workspace_name'] = workspace.name
                    tab_node['tab_id'] = tab.id
                    tab_node['tab_name'] = tab.name

                    for j in range(tab.toolbarPanels.count):
                        try:
                            panel = tab.toolbarPanels.item(j)
                            panel_node = serialize_item(panel, 'Toolbar Panel')
                            # panel_node['workspace_id'] = workspace.id
                            # panel_node['workspace_name'] = workspace.name
                            # panel_node['tab_id'] = tab.id
                            # panel_node['tab_name'] = tab.name
                            panel_node['panel_id'] = panel.id
                            panel_node['panel_name'] = panel.name

                            control: adsk.core.CommandControl
                            for control in panel.controls:
                                control_node = serialize_control(control)
                                panel_node['children'].append(control_node)

                            tab_node['children'].append(panel_node)

                        except:
                            fus.handle_error(F'Failed to get panel at INDEX {j} in tab: {tab.name}\n')

                    workspace_node['children'].append(tab_node)
                except:
                    fus.handle_error(f'Failed getting tab at INDEX {i} in workspace: {workspace.name}\n')

            if len(workspace_node['children']) > 2:
                root_nodes.append(workspace_node)

    for toolbar in ui.toolbars:
        fus.log(f'*********************| Toolbar: {toolbar.id} |*********************')
        toolbar_node = serialize_item(toolbar, 'Toolbar')

        control: adsk.core.CommandControl
        for control in toolbar.controls:
            control_node = serialize_control(control)
            toolbar_node['children'].append(control_node)

        if len(toolbar_node['children']) > 2:
            root_nodes.append(toolbar_node)

    if len(NO_NAME_DROPDOWNS) > 0:
        fus.handle_error(F'Dropdown Controls had no "name" property:{NO_NAME_DROPDOWNS}\n')

    return {'core': root_nodes}


def make_addin_text(node_data):
    workspace_name = node_data.get('workspace_name', 'No valid Workspace for item')
    workspace_id = node_data.get('workspace_id', '')
    tab_id = node_data.get('tab_id', '')
    tab_name = node_data.get('tab_name', '')
    panel_id = node_data.get('panel_id', '')
    panel_name = node_data.get('panel_name', '')
    control_id = node_data.get('control_id', '')
    control_name = node_data.get('control_name', '')

    msg = "-- Selected Item --\n"

    if len(workspace_name) > 0:
        msg += f"WORKSPACE_NAME = {workspace_name}\n"
    if len(workspace_id) > 0:
        msg += f"WORKSPACE_ID = {workspace_id}\n"
    if len(tab_id) > 0:
        msg += f"TAB_ID = {tab_id}\n"
    if len(tab_name) > 0:
        msg += f"TAB_NAME = {tab_name}\n"
    if len(panel_id) > 0:
        msg += f"PANEL_ID = {panel_id}\n"
    if len(panel_name) > 0:
        msg += f"PANEL_NAME = {panel_name}\n"
    if len(control_id) > 0:
        msg += f"CONTROL_ID = {control_id}\n"
    if len(control_name) > 0:
        msg += f"CONTROL_NAME = {control_name}\n"

    return msg
