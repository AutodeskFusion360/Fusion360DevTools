import json
import os

import adsk.core
import adsk.fusion

from ... import config
from ...lib import fusion360utils as futil

app = adsk.core.Application.get()
ui = app.userInterface

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
local_handlers = []
create_handlers = []
execute_handlers = []
ui_starting_handlers = []
ui_terminated_handlers = []
ui_terminated_handlers_run = []

std_commands = ['SelectCommand', 'CommitCommand']
capture_commands = []

value_types = [adsk.core.BoolValueCommandInput.classType(), adsk.core.DistanceValueCommandInput.classType(),
               adsk.core.FloatSpinnerCommandInput.classType(),
               adsk.core.IntegerSpinnerCommandInput.classType(),
               adsk.core.ValueCommandInput.classType(),
               adsk.core.StringValueCommandInput.classType()]

slider_types = [adsk.core.FloatSliderCommandInput.classType(),
                adsk.core.IntegerSliderCommandInput.classType()]

list_types = [adsk.core.ButtonRowCommandInput.classType(), adsk.core.DropDownCommandInput.classType(),
              adsk.core.RadioButtonGroupCommandInput.classType()]

selection_types = [adsk.core.SelectionCommandInput.classType()]

string_types = [adsk.core.TextBoxCommandInput.classType()]


def start_recording():
    ui_starting_handlers.append(
        futil.add_handler(ui.commandStarting, ui_command_starting, local_handlers=local_handlers))
    ui_terminated_handlers.append(
        futil.add_handler(ui.commandTerminated, ui_command_terminated, local_handlers=local_handlers))


def stop_recording():
    global local_handlers
    local_handlers = []
    clear_ui_handlers()


def clear_ui_handlers():
    global ui_starting_handlers
    global ui_terminated_handlers

    for starting_handler in ui_starting_handlers:
        ui.commandStarting.remove(starting_handler)
    ui_starting_handlers = []

    for terminated_handler in ui_terminated_handlers:
        ui.commandTerminated.remove(terminated_handler)
    ui_terminated_handlers = []


def ui_command_starting(args: adsk.core.ApplicationCommandEventArgs):
    global create_handlers

    futil.log(f'In ui_command_starting event handler for: {args.commandId}')

    cmd_def = args.commandDefinition
    if args.commandId not in std_commands:
        if args.commandId not in capture_commands:
            capture_commands.append(args.commandId)

            app_dir = get_user_app_dir(config.ADDIN_NAME)
            fusion_file_name = os.path.join(app_dir, args.commandId + '_start.f3d')

            design = adsk.fusion.Design.cast(app.activeDocument.products.itemByProductType('DesignProductType'))
            export_manager = design.exportManager
            fusion_options = export_manager.createFusionArchiveExportOptions(fusion_file_name)
            export_manager.execute(fusion_options)

            create_handlers.append(
                futil.add_handler(cmd_def.commandCreated, cmd_created_record, local_handlers=local_handlers))


def ui_command_terminated(args: adsk.core.ApplicationCommandEventArgs):
    global create_handlers

    futil.log(f'In ui_command_terminated event handler for: {args.commandId}')

    if args.commandId not in std_commands:

        app_dir = get_user_app_dir(config.ADDIN_NAME)
        fusion_file_name = os.path.join(app_dir, args.commandId + '_result.f3d')

        design = adsk.fusion.Design.cast(app.activeDocument.products.itemByProductType('DesignProductType'))
        export_manager = design.exportManager
        fusion_options = export_manager.createFusionArchiveExportOptions(fusion_file_name)
        export_manager.execute(fusion_options)

        for cmd_event in create_handlers:
            args.commandDefinition.commandCreated.remove(cmd_event)
        create_handlers = []
        if args.commandId in capture_commands:
            capture_commands.remove(args.commandId)


def ui_command_terminated_run(args: adsk.core.ApplicationCommandEventArgs):
    global create_handlers
    global ui_terminated_handlers_run
    futil.log(f'In ui_command_terminated_run event handler for: {args.commandId}')

    app_dir = get_user_app_dir(config.ADDIN_NAME)
    input_file = os.path.join(app_dir, args.commandId + '.json')
    with open(input_file) as json_file:
        input_values = json.load(json_file)

    design = adsk.fusion.Design.cast(app.activeDocument.products.itemByProductType('DesignProductType'))
    physical_props = design.rootComponent.physicalProperties

    tolerance = .00001
    results = {
        'volume': input_values['volume'] - physical_props.volume < tolerance,
        'mass': input_values['mass'] - physical_props.mass < tolerance,
        'com_x': input_values['com_x'] - physical_props.centerOfMass.x < tolerance,
        'com_y': input_values['com_y'] - physical_props.centerOfMass.y < tolerance,
        'com_z': input_values['com_z'] - physical_props.centerOfMass.z < tolerance,
    }

    for cmd_event in create_handlers:
        args.commandDefinition.commandCreated.remove(cmd_event)
    create_handlers = []
    if args.commandId in capture_commands:
        capture_commands.remove(args.commandId)

    for ui_event_handler in ui_terminated_handlers_run:
        ui.commandTerminated.remove(ui_event_handler)

    ui_terminated_handlers_run = []

    ui.messageBox(f"Did Test Pass:\n{str(results)}")


def cmd_created_record(args: adsk.core.CommandCreatedEventArgs):
    global execute_handlers

    futil.log(f'In cmd_created event handler for: {args.command.parentCommandDefinition.id}')

    execute_handlers.append(
        futil.add_handler(args.command.execute, cmd_execute_all, name='execute', local_handlers=local_handlers))
    execute_handlers.append(
        futil.add_handler(args.command.executePreview, cmd_preview_record, name='executePreview',
                          local_handlers=local_handlers))

    for cmd_input in args.command.commandInputs:
        futil.log(f'cmd_created - {cmd_input.name} - {cmd_input.id}')


def run_test(command_id: str):
    command_def = ui.commandDefinitions.itemById(command_id)

    app_dir = get_user_app_dir(config.ADDIN_NAME)

    fusion_file_name = os.path.join(app_dir, command_id + '_start.f3d')

    import_manager = app.importManager
    fusion_options = import_manager.createFusionArchiveImportOptions(fusion_file_name)
    new_document = import_manager.importToNewDocument(fusion_options)
    new_document.activate()

    create_handlers.append(
        futil.add_handler(command_def.commandCreated, cmd_created_run, local_handlers=local_handlers))

    ui_terminated_handlers_run.append(
        futil.add_handler(ui.commandTerminated, ui_command_terminated_run, local_handlers=local_handlers))

    command_def.execute()


def cmd_created_run(args: adsk.core.CommandCreatedEventArgs):
    app_dir = get_user_app_dir(config.ADDIN_NAME)

    input_file = os.path.join(app_dir, args.command.parentCommandDefinition.id + '.json')
    with open(input_file) as json_file:
        input_values = json.load(json_file)

    set_inputs(args.command.commandInputs, input_values)

    commit = ui.commandDefinitions.itemById('CommitCommand')
    commit.execute()


def cmd_preview_record(args: adsk.core.CommandEventArgs):
    global execute_handlers
    futil.log(f'In cmd_preview event handler ({args.firingEvent.name}) for: {args.command.parentCommandDefinition.id}')

    input_values = get_inputs(args.command.commandInputs)

    design = adsk.fusion.Design.cast(app.activeDocument.products.itemByProductType('DesignProductType'))
    physical_props = design.rootComponent.physicalProperties

    input_values['volume'] = physical_props.volume
    input_values['mass'] = physical_props.mass
    input_values['com_x'] = physical_props.centerOfMass.x
    input_values['com_y'] = physical_props.centerOfMass.y
    input_values['com_z'] = physical_props.centerOfMass.z

    futil.log(f'input_values:\n {json.dumps(input_values, indent=4)}')

    app_dir = get_user_app_dir(config.ADDIN_NAME)
    output_file = os.path.join(app_dir, args.command.parentCommandDefinition.id + '.json')
    with open(output_file, 'w') as outfile:
        outfile.write(json.dumps(input_values, indent=4))


def cmd_execute_all(args: adsk.core.CommandEventArgs):
    global execute_handlers
    futil.log(f'In cmd_executed event handler ({args.firingEvent.name}) for: {args.command.parentCommandDefinition.id}')

    for cmd_event in execute_handlers:
        args.command.execute.remove(cmd_event)
    execute_handlers = []


def get_inputs(command_inputs: adsk.core.CommandInputs):
    input_values = {}

    for command_input in command_inputs:

        if command_input.objectType in value_types:
            input_values[command_input.id] = command_input.value

        elif command_input.objectType in slider_types:
            input_values[command_input.id] = command_input.valueOne

        elif command_input.objectType in string_types:
            input_values[command_input.id] = command_input.text

        elif command_input.objectType in list_types:
            if command_input.objectType == adsk.core.DropDownCommandInput.classType():
                if command_input.dropDownStyle == adsk.core.DropDownStyles.CheckBoxDropDownStyle:
                    input_values[command_input.id] = command_input.listItems
                else:
                    if command_input.selectedItem is not None:
                        input_values[command_input.id] = command_input.selectedItem.name
            else:
                if command_input.selectedItem is not None:
                    input_values[command_input.id] = command_input.selectedItem.name
                else:
                    input_values[command_input.id] = None

        elif command_input.objectType in selection_types:
            selections = []
            if command_input.selectionCount > 0:
                for i in range(0, command_input.selectionCount):
                    selections.append(command_input.selection(i).entity.entityToken)

            input_values[command_input.id] = selections

        else:
            input_values[command_input.id] = command_input.name

    return input_values


def set_inputs(command_inputs: adsk.core.CommandInputs, input_values: dict):
    for command_input in command_inputs:
        command_value = input_values.get(command_input.id, False)

        if not command_value:
            pass

        elif command_input.objectType in value_types:
            command_input.value = input_values[command_input.id]

        elif command_input.objectType in slider_types:
            command_input.valueOne = input_values[command_input.id]

        elif command_input.objectType in string_types:
            command_input.text = input_values[command_input.id]

        # TODO
        # elif command_input.objectType in list_types:
        #     if command_input.objectType == adsk.core.DropDownCommandInput.classType():
        #         if command_input.dropDownStyle == adsk.core.DropDownStyles.CheckBoxDropDownStyle:
        #             input_values[command_input.id] = command_input.listItems
        #         else:
        #             if command_input.selectedItem is not None:
        #                 input_values[command_input.id] = command_input.selectedItem.name
        #     else:
        #         if command_input.selectedItem is not None:
        #             input_values[command_input.id] = command_input.selectedItem.name
        #         else:
        #             input_values[command_input.id] = None

        elif command_input.objectType in selection_types:
            for entity_token in input_values[command_input.id]:
                design: adsk.fusion.Design = app.activeDocument.products.itemByProductType('DesignProductType')
                entities = design.findEntityByToken(entity_token)
                command_input.addSelection(entities[0])

        else:
            # TODO???
            pass

    return input_values


def get_user_app_dir(user_dir_name: str) -> str:
    """Creates a directory in the user's home folder to store data related to this app

    Args:
        user_dir_name: Name of the directory in user home
    """

    # Get user's home directory
    default_dir = os.path.expanduser("~")

    # Create a subdirectory for this application settings
    default_dir = os.path.join(default_dir, user_dir_name, "")

    # Create the folder if it does not exist
    if not os.path.exists(default_dir):
        os.makedirs(default_dir)

    return default_dir
