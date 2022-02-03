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

import json
import os

import adsk.core
import adsk.fusion

from ... import config
from ...lib import fusion360utils as futil

app = adsk.core.Application.get()
ui = app.userInterface

# Tolerance for geometry checking
TOLERANCE = .00001

# Local list of event handlers used to maintain a reference so
# they are not released and garbage collected.
create_handlers = []
create_handlers_dict = {}
preview_handlers = []
ui_starting_handlers = []
ui_terminated_handlers = []

NO_RECORD_COMMANDS = ['SelectCommand', 'CommitCommand',
                      f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_start',
                      f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_stop',
                      f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_run']
capture_commands = []

CURRENT_TEST_NAME = ''

CURRENT_INPUT_VALUES = {}

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


def clear_ui_handlers():
    global ui_starting_handlers
    global ui_terminated_handlers

    for starting_handler in ui_starting_handlers:
        ui.commandStarting.remove(starting_handler)
    ui_starting_handlers = []

    for terminated_handler in ui_terminated_handlers:
        ui.commandTerminated.remove(terminated_handler)
    ui_terminated_handlers = []


def clear_cmd_handlers(command_def: adsk.core.CommandDefinition):
    global create_handlers_dict
    global capture_commands
    global preview_handlers
    global create_handlers

    create_handlers = []
    preview_handlers = []

    command_create_event = create_handlers_dict.get(command_def.id, False)
    if command_create_event:
        command_def.commandCreated.remove(command_create_event)
        del create_handlers_dict[command_def.id]

    # TODO Best way?
    if command_def.id in capture_commands:
        capture_commands.remove(command_def.id)


def start_recording(test_name: str):
    global CURRENT_TEST_NAME
    CURRENT_TEST_NAME = test_name

    export_active_document('start')

    futil.add_handler(ui.commandStarting, record_command_starting, local_handlers=ui_starting_handlers)
    futil.add_handler(ui.commandTerminated, record_command_terminated, local_handlers=ui_terminated_handlers)


def stop_recording():
    futil.log(f'Stop Recording')
    clear_ui_handlers()

    for command_id in create_handlers_dict.keys():
        command_def = ui.commandDefinitions.itemById(command_id)
        if command_def:
            clear_cmd_handlers(command_def)


def record_command_starting(args: adsk.core.ApplicationCommandEventArgs):
    global create_handlers_dict

    futil.log(f'In record_command_starting event handler for: {args.commandId}')

    command_def = args.commandDefinition
    if args.commandId not in NO_RECORD_COMMANDS:
        if args.commandId not in capture_commands:
            capture_commands.append(args.commandId)

            create_handlers_dict[command_def.id] = futil.add_handler(command_def.commandCreated, record_cmd_created,
                                                                     local_handlers=create_handlers)


def record_cmd_created(args: adsk.core.CommandCreatedEventArgs):
    global preview_handlers
    global CURRENT_INPUT_VALUES

    CURRENT_INPUT_VALUES = {}
    futil.log(f'In record_cmd_created event handler for: {args.command.parentCommandDefinition.id}')

    futil.add_handler(args.command.executePreview, record_cmd_preview, name='executePreview',
                      local_handlers=preview_handlers)


def record_cmd_preview(args: adsk.core.CommandEventArgs):
    global CURRENT_INPUT_VALUES
    futil.log(
        f'In record_cmd_preview event handler for: {args.command.parentCommandDefinition.id}')

    CURRENT_INPUT_VALUES = get_inputs(args.command.commandInputs)
    CURRENT_INPUT_VALUES['command_id'] = args.command.parentCommandDefinition.id
    futil.log(f'CURRENT_INPUT_VALUES:\n {json.dumps(CURRENT_INPUT_VALUES, indent=4)}')


def record_command_terminated(args: adsk.core.ApplicationCommandEventArgs):
    futil.log(f'In record_command_terminated event handler for: {args.commandId}')

    if args.commandId not in NO_RECORD_COMMANDS:
        write_physical_properties()
        write_dict_to_json(CURRENT_INPUT_VALUES, 'input_values')
        export_active_document('stop')

        clear_cmd_handlers(args.commandDefinition)


def run_test(test_name: str):
    global CURRENT_TEST_NAME
    CURRENT_TEST_NAME = test_name

    # TODO Should be a loop
    input_values = read_dict_from_json('input_values')
    command_def = ui.commandDefinitions.itemById(input_values['command_id'])
    import_fusion_file(test_name, 'start')

    create_handlers_dict[command_def.id] = futil.add_handler(command_def.commandCreated, run_cmd_created,
                                                             local_handlers=create_handlers)

    futil.add_handler(ui.commandTerminated, run_cmd_terminated, local_handlers=ui_terminated_handlers)

    command_def.execute()


def run_cmd_created(args: adsk.core.CommandCreatedEventArgs):
    futil.log(f'In run_cmd_created event handler for: {args.command.parentCommandDefinition.id}')

    input_values = read_dict_from_json('input_values')
    set_inputs(args.command.commandInputs, input_values)

    # FIXME Should be in custom event maybe?
    commit = ui.commandDefinitions.itemById('CommitCommand')
    commit.execute()


def run_cmd_terminated(args: adsk.core.ApplicationCommandEventArgs):
    futil.log(f'In run_cmd_terminated event handler for: {args.commandId}')

    if args.commandId not in NO_RECORD_COMMANDS:
        clear_cmd_handlers(args.commandDefinition)

    if len(create_handlers_dict.keys()) == 0:
        clear_ui_handlers()
        compare_physical_results()


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

        # TODO need to figure this out
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
            # TODO Missing Tables, etc.???
            pass

    return input_values


def get_user_app_dir(app_name: str) -> str:
    user_dir = os.path.expanduser("~")
    app_dir = os.path.join(user_dir, app_name, "")
    if not os.path.exists(app_dir):
        os.makedirs(app_dir)
    return app_dir


def get_test_base_dir() -> str:
    app_dir = get_user_app_dir(config.ADDIN_NAME)

    test_base_dir = os.path.join(app_dir, 'TESTS', "")
    if not os.path.exists(test_base_dir):
        os.makedirs(test_base_dir)

    return test_base_dir


def get_test_dir(test_name: str) -> str:
    test_base_dir = get_test_base_dir()

    test_dir = os.path.join(test_base_dir, test_name, "")
    if not os.path.exists(test_dir):
        os.makedirs(test_dir)

    return test_dir


def export_active_document(file_name: str):
    test_dir = get_test_dir(CURRENT_TEST_NAME)
    fusion_file_name = os.path.join(test_dir, file_name + '.f3d')

    design = adsk.fusion.Design.cast(app.activeDocument.products.itemByProductType('DesignProductType'))
    export_manager = design.exportManager
    fusion_options = export_manager.createFusionArchiveExportOptions(fusion_file_name)
    export_manager.execute(fusion_options)


def write_dict_to_json(the_dict: dict, file_name: str):
    test_dir = get_test_dir(CURRENT_TEST_NAME)
    output_file = os.path.join(test_dir, file_name + '.json')
    with open(output_file, 'w') as outfile:
        outfile.write(json.dumps(the_dict, indent=4))


def read_dict_from_json(file_name: str) -> dict:
    test_dir = get_test_dir(CURRENT_TEST_NAME)
    input_file = os.path.join(test_dir, file_name + '.json')
    with open(input_file) as json_file:
        the_dict = json.load(json_file)
    return the_dict


def import_fusion_file(test_name: str, file_name: str):
    test_dir = get_test_dir(test_name)
    fusion_file_name = os.path.join(test_dir, file_name + '.f3d')

    import_manager = app.importManager
    fusion_options = import_manager.createFusionArchiveImportOptions(fusion_file_name)
    new_document = import_manager.importToNewDocument(fusion_options)
    new_document.activate()


def write_physical_properties():
    result_values = get_root_physical_props()
    write_dict_to_json(result_values, 'results')


def compare_physical_results():
    original_values = read_dict_from_json('results')
    new_values = get_root_physical_props()

    compare_results = {}

    for key, value in original_values.items():
        new_value = new_values.get(key, False)
        if new_value:
            compare_results[key] = abs(original_values[key] - new_values[key]) < TOLERANCE

    ui.messageBox(f"{json.dumps(compare_results, indent=4)}", "Geometry Comparison - Test Results")


def get_root_physical_props() -> dict:
    design = adsk.fusion.Design.cast(app.activeDocument.products.itemByProductType('DesignProductType'))
    physical_props = design.rootComponent.getPhysicalProperties(adsk.fusion.CalculationAccuracy.HighCalculationAccuracy)
    property_values = {
        'volume': physical_props.volume,
        'mass': physical_props.mass,
        'com_x': physical_props.centerOfMass.x,
        'com_y': physical_props.centerOfMass.y,
        'com_z': physical_props.centerOfMass.z
    }
    futil.log(f'get_root_physical_props:\n {json.dumps(property_values, indent=4)}')
    return property_values
