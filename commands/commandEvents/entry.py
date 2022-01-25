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
preview_handlers = []

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


# Executed when add-in is run.
def start():
    # Create the event handler for when data files are complete.
    # futil.add_handler(ui.commandCreated, ui_command_created, local_handlers=local_handlers)
    futil.add_handler(ui.commandStarting, ui_command_starting, local_handlers=local_handlers)
    futil.add_handler(ui.commandTerminated, ui_command_terminated, local_handlers=local_handlers)


# Executed when add-in is stopped.
def stop():
    global local_handlers
    local_handlers = []


# Function to be executed by the dataFileComplete event.
def ui_command_created(args: adsk.core.ApplicationCommandEventArgs):
    futil.log(f'In ui_command_created event handler for: {args.commandId}')


# Function to be executed by the dataFileComplete event.
def ui_command_starting(args: adsk.core.ApplicationCommandEventArgs):
    global create_handlers

    futil.log(f'In ui_command_starting event handler for: {args.commandId}')

    cmd_def = args.commandDefinition
    if args.commandId not in std_commands:
        if args.commandId not in capture_commands:
            capture_commands.append(args.commandId)
            create_handlers.append(
                futil.add_handler(cmd_def.commandCreated, cmd_created, local_handlers=local_handlers))


# Function to be executed by the dataFileComplete event.
def ui_command_terminated(args: adsk.core.ApplicationCommandEventArgs):
    global create_handlers

    futil.log(f'In ui_command_terminated event handler for: {args.commandId}')

    if args.commandId not in std_commands:
        for cmd_event in create_handlers:
            args.commandDefinition.commandCreated.remove(cmd_event)
        create_handlers = []
        capture_commands.remove(args.commandId)


# Function to be executed by the dataFileComplete event.
def cmd_created(args: adsk.core.CommandCreatedEventArgs):
    global preview_handlers

    futil.log(f'In cmd_created event handler for: {args.command.parentCommandDefinition.id}')

    execute_handlers.append(
        futil.add_handler(args.command.execute, cmd_executed, name='execute', local_handlers=local_handlers))
    execute_handlers.append(
        futil.add_handler(args.command.executePreview, cmd_preview, name='executePreview', local_handlers=local_handlers))

    for cmd_input in args.command.commandInputs:
        futil.log(f'cmd_created - {cmd_input.name} - {cmd_input.id}')
    

    app_dir = get_user_app_dir(config.ADDIN_NAME)
    input_file = os.path.join(app_dir, args.command.parentCommandDefinition.id + '.json')

    with open(input_file) as json_file:
        input_values = json.load(json_file)

    set_inputs(args.command.commandInputs, input_values)


# Function to be executed by the dataFileComplete event.
def cmd_preview(args: adsk.core.CommandEventArgs):
    global preview_handlers
    futil.log(f'In cmd_preview event handler ({args.firingEvent.name}) for: {args.command.parentCommandDefinition.id}')

    # for cmd_input in args.command.commandInputs:
    #     futil.log(f'cmd_input.id: {cmd_input.id}')
    #     try:
    #         futil.log(f'cmd_input.value: {cmd_input.value}')
    #     except:
    #         pass

    selection_input: adsk.core.SelectionCommandInput = args.command.commandInputs.itemById('selection_input')
    futil.log(f'Selection Count cmd_preview: {selection_input.selectionCount}')

    input_values = get_inputs(args.command.commandInputs)

    futil.log(f'input_values:\n {json.dumps(input_values, indent=4)}')

    app_dir = get_user_app_dir(config.ADDIN_NAME)
    output_file = os.path.join(app_dir, args.command.parentCommandDefinition.id + '.json')
    with open(output_file, 'w') as outfile:
        outfile.write(json.dumps(input_values, indent=4))


# Function to be executed by the dataFileComplete event.
def cmd_executed(args: adsk.core.CommandEventArgs):
    global preview_handlers
    futil.log(f'In cmd_executed event handler ({args.firingEvent.name}) for: {args.command.parentCommandDefinition.id}')

    # for cmd_input in args.command.commandInputs:
    #     futil.log(f'cmd_input.id: {cmd_input.id}')
    #     try:
    #         futil.log(f'cmd_input.value: {cmd_input.value}')
    #     except:
    #         pass

    # selection_input: adsk.core.SelectionCommandInput = args.command.commandInputs.itemById('selection_input')
    # futil.log(f'Selection Count cmd_executed: {selection_input.selectionCount}')
    #
    # input_values = get_inputs(args.command.commandInputs)
    #
    # futil.log(f'input_values:\n {json.dumps(input_values, indent=4)}')

    for cmd_event in execute_handlers:
        args.command.execute.remove(cmd_event)
    execute_handlers = []


def get_inputs(command_inputs: adsk.core.CommandInputs):

    input_values = {}

    for command_input in command_inputs:

        # If the input type is in this list the value of the input is returned
        if command_input.objectType in value_types:
            input_values[command_input.id] = command_input.value
            # input_values[command_input.id + '_input'] = command_input

        elif command_input.objectType in slider_types:
            input_values[command_input.id] = command_input.valueOne
            # input_values[command_input.id + '_input'] = command_input

        elif command_input.objectType in string_types:
            input_values[command_input.id] = command_input.text
            # input_values[command_input.id + '_input'] = command_input

        # TODO need to account for radio and button multi select also
        # If the input type is in this list the name of the selected list item is returned
        elif command_input.objectType in list_types:
            if command_input.objectType == adsk.core.DropDownCommandInput.classType():
                if command_input.dropDownStyle == adsk.core.DropDownStyles.CheckBoxDropDownStyle:
                    input_values[command_input.id] = command_input.listItems
                    # input_values[command_input.id + '_input'] = command_input

                else:
                    if command_input.selectedItem is not None:
                        input_values[command_input.id] = command_input.selectedItem.name
                        # input_values[command_input.id + '_input'] = command_input
            else:
                if command_input.selectedItem is not None:
                    input_values[command_input.id] = command_input.selectedItem.name
                else:
                    input_values[command_input.id] = None
                # input_values[command_input.id + '_input'] = command_input

        # If the input type is a selection an array of entities is returned
        elif command_input.objectType in selection_types:
            futil.log(f'Selection Count get inputs: {command_input.selectionCount}')
            selections = []
            if command_input.selectionCount > 0:
                for i in range(0, command_input.selectionCount):
                    selections.append(command_input.selection(i).entity.entityToken)

            input_values[command_input.id] = selections
            # input_values[command_input.id + '_input'] = command_input

        else:
            input_values[command_input.id] = command_input.name
            # input_values[command_input.id + '_input'] = command_input

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
            input_values[command_input.id] = command_input.name
            # input_values[command_input.id + '_input'] = command_input

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
