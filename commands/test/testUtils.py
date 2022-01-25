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
local_handlers = []
create_handlers = []
preview_handlers = []
ui_starting_handlers = []
ui_terminated_handlers = []

NO_RECORD_COMMANDS = ['SelectCommand', 'CommitCommand',
                      f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_start',
                      f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_stop',
                      f'{config.COMPANY_NAME}_{config.ADDIN_NAME}_record']
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


def clear_cmd_handlers(cmd_def: adsk.core.CommandDefinition):
    global create_handlers
    global capture_commands
    global preview_handlers
    for cmd_event in create_handlers:
        cmd_def.commandCreated.remove(cmd_event)
    create_handlers = []
    preview_handlers = []

    # TODO Best way?
    if cmd_def.id in capture_commands:
        capture_commands.remove(cmd_def.id)


def start_recording(test_name: str):
    global CURRENT_TEST_NAME
    CURRENT_TEST_NAME = test_name
    export_active_document('start')

    ui_starting_handlers.append(
        futil.add_handler(ui.commandStarting, record_command_starting, local_handlers=local_handlers))
    ui_terminated_handlers.append(
        futil.add_handler(ui.commandTerminated, record_command_terminated, local_handlers=local_handlers))


def stop_recording():
    global local_handlers
    local_handlers = []
    clear_ui_handlers()


def record_command_starting(args: adsk.core.ApplicationCommandEventArgs):
    global create_handlers

    futil.log(f'In record_command_starting event handler for: {args.commandId}')

    cmd_def = args.commandDefinition
    if args.commandId not in NO_RECORD_COMMANDS:
        if args.commandId not in capture_commands:
            capture_commands.append(args.commandId)

            create_handlers.append(
                futil.add_handler(cmd_def.commandCreated, record_cmd_created, local_handlers=local_handlers))


def record_cmd_created(args: adsk.core.CommandCreatedEventArgs):
    global preview_handlers
    global CURRENT_INPUT_VALUES
    CURRENT_INPUT_VALUES = {}
    futil.log(f'In record_cmd_created event handler for: {args.command.parentCommandDefinition.id}')

    # execute_handlers.append(
    #     futil.add_handler(args.command.execute, cmd_execute, name='execute', local_handlers=local_handlers))
    preview_handlers.append(
        futil.add_handler(args.command.executePreview, record_cmd_preview, name='executePreview',
                          local_handlers=local_handlers))


def record_cmd_preview(args: adsk.core.CommandEventArgs):
    global CURRENT_INPUT_VALUES
    futil.log(f'In cmd_preview event handler ({args.firingEvent.name}) for: {args.command.parentCommandDefinition.id}')

    CURRENT_INPUT_VALUES = get_inputs(args.command.commandInputs)
    CURRENT_INPUT_VALUES['command_id'] = args.command.parentCommandDefinition.id
    futil.log(f'CURRENT_INPUT_VALUES:\n {json.dumps(CURRENT_INPUT_VALUES, indent=4)}')


def cmd_execute(args: adsk.core.CommandEventArgs):
    global preview_handlers
    futil.log(f'In cmd_executed event handler ({args.firingEvent.name}) for: {args.command.parentCommandDefinition.id}')

    for cmd_event in preview_handlers:
        args.command.execute.remove(cmd_event)
    preview_handlers = []


def record_command_terminated(args: adsk.core.ApplicationCommandEventArgs):
    futil.log(f'In ui_command_terminated event handler for: {args.commandId}')

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

    create_handlers.append(
        futil.add_handler(command_def.commandCreated, run_cmd_created, local_handlers=local_handlers))

    ui_terminated_handlers.append(
        futil.add_handler(ui.commandTerminated, run_cmd_terminated, local_handlers=local_handlers))

    command_def.execute()


def run_cmd_created(args: adsk.core.CommandCreatedEventArgs):
    futil.log(f'In run_cmd_created event handler for: {args.command.parentCommandDefinition.id}')

    input_values = read_dict_from_json('input_values')
    set_inputs(args.command.commandInputs, input_values)

    # FIXME Should be in custom event maybe?
    commit = ui.commandDefinitions.itemById('CommitCommand')
    commit.execute()


def run_cmd_terminated(args: adsk.core.ApplicationCommandEventArgs):
    futil.log(f'In ui_command_terminated_run event handler for: {args.commandId}')

    clear_cmd_handlers(args.commandDefinition)
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


def write_physical_properties():
    design = adsk.fusion.Design.cast(app.activeDocument.products.itemByProductType('DesignProductType'))
    physical_props = design.rootComponent.physicalProperties
    result_values = {
        'volume': physical_props.volume,
        'mass': physical_props.mass,
        'com_x': physical_props.centerOfMass.x,
        'com_y': physical_props.centerOfMass.y,
        'com_z': physical_props.centerOfMass.z
    }
    write_dict_to_json(result_values, 'results')


def get_user_app_dir(app_dir_name: str) -> str:
    user_dir = os.path.expanduser("~")
    app_dir = os.path.join(user_dir, app_dir_name, "")
    if not os.path.exists(app_dir):
        os.makedirs(app_dir)
    return app_dir


def get_test_dir(test_name: str) -> str:
    app_dir = get_user_app_dir(config.ADDIN_NAME)
    test_dir = os.path.join(app_dir, test_name, "")
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


def read_dict_from_json(file_name: str):
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


def compare_physical_results():
    result_values = read_dict_from_json('results')

    design = adsk.fusion.Design.cast(app.activeDocument.products.itemByProductType('DesignProductType'))
    physical_props = design.rootComponent.physicalProperties
    results = {
        'volume': result_values['volume'] - physical_props.volume < TOLERANCE,
        'mass': result_values['mass'] - physical_props.mass < TOLERANCE,
        'com_x': result_values['com_x'] - physical_props.centerOfMass.x < TOLERANCE,
        'com_y': result_values['com_y'] - physical_props.centerOfMass.y < TOLERANCE,
        'com_z': result_values['com_z'] - physical_props.centerOfMass.z < TOLERANCE,
    }

    ui.messageBox(f"Did Test Pass:\n{str(results)}")

