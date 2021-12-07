import inspect
import json
import sys
import types

import adsk.core
import adsk.fusion
from ...lib import fusion360utils as fus

object_dict = {}
click_dict = {}
click_stack = []
original_selection_name = ''
original_selection = None


def initialize_stack():
    global click_stack
    global click_dict
    global original_selection_name
    global original_selection
    original_selection_name = ''
    original_selection = None
    click_stack = []
    click_dict = {}


def set_selection(selected_object):
    global original_selection_name
    global original_selection
    original_selection_name = selected_object.objectType
    original_selection = selected_object


def make_node_name(name, value):
    text = f"<b>{name}</b>: {value}",
    return text


def make_enum_node(param_name, this_object):
    # my_obj = axis  # From Selection or navigation
    # param_name = 'healthState'  # From object parameters

    if hasattr(this_object, f'_get_{param_name}'):
        e_name = inspect.signature(getattr(this_object, f'_get_{param_name}')).return_annotation.split('::')
        if e_name[0] == 'adsk':
            e_value = inspect.getmembers(getattr(sys.modules[f'{e_name[0]}.{e_name[1]}'],
                                         e_name[2]), lambda x: (x == getattr(this_object, param_name)))[0][0]

            class_name = f'{e_name[0]}.{e_name[1]}.{e_name[2]}'

            display_name = f'{class_name}.{e_value}'

            return {
                'text': make_node_name(param_name, display_name),
                'children': [],
                'type': '5-enum',
                'param_name': param_name,
                'clickable': False,
            }
    return make_node(param_name, getattr(this_object, param_name))


def make_node(param_name, this_obj):
    global object_dict
    global click_dict

    if hasattr(this_obj, 'objectType'):
        node_name = make_node_name(param_name, this_obj.objectType)
        clickable = True
        click_dict[param_name] = this_obj
        node_type = '3-object'

    elif isinstance(this_obj, types.MethodType):
        node_name = make_node_name(param_name, 'ADSK Method')
        clickable = False
        node_type = '1-method'

    else:
        node_name = make_node_name(param_name, str(this_obj))
        clickable = False
        node_type = '2-property'

    new_node = {
        'text': node_name,
        'children': [],
        'type': node_type,
        'param_name': param_name,
        'clickable': clickable,
    }
    return new_node


def get_object_tree(selection: adsk.core.Base):
    global object_dict
    global click_dict
    click_dict = {}
    tree_nodes = []
    object_dict = {}
    for param_name in dir(selection):
        if not param_name.startswith('_'):
            try:
                object_dict[param_name] = selection.__getattribute__(param_name)
            except:
                fus.handle_error(f'Broken: {param_name}')

    for param_name, this_object in object_dict.items():
        if param_name == 'item':
            node_name = make_node_name(param_name, 'ADSK Collection')
            clickable = False
            children = []
            for index in range(selection.count):
                sub_object = selection.item(index)
                sub_key = f'{param_name}({index})'

                children.append(make_node(str(sub_key), sub_object))

                click_dict[sub_key] = sub_object

            new_node = {
                'text': node_name,
                'children': children,
                'type': '4-collection',
                'param_name': param_name,
                'clickable': clickable,
            }
        elif isinstance(this_object, int):
            new_node = make_enum_node(param_name, selection)

        else:
            new_node = make_node(param_name, this_object)

        tree_nodes.append(new_node)

    title = get_title(selection.objectType)
    tree_data = {
        'core': tree_nodes,
        'title_string': title,
    }
    return tree_data


def get_new_tree(key):
    new_object = click_dict[key]
    click_stack.append({
        'name': key,
        'object': new_object
    })
    new_tree = get_object_tree(new_object)
    if hasattr(new_object, 'objectType'):
        name = f'{key} : {new_object.objectType}'
    else:
        name = key
    title = get_title(name)
    new_tree['title_string'] = title
    return new_tree


def get_object_path():
    return '<b>SelectedEntity</b>' + ''.join([f".{click_object['name']}" for click_object in click_stack])


def get_title(name):

    title_obj = {
        'object_name': name,
        'object_path': get_object_path(),
        'original_selection_name': original_selection_name,
    }
    return json.dumps(title_obj)


def get_end_title(end_param_name):
    base_object_path = get_object_path()

    title_obj = {
        'object_path': f'{base_object_path}.{end_param_name}',
        'original_selection_name': original_selection_name,
    }

    return {'title_string': json.dumps(title_obj)}


def go_back():
    if len(click_stack) > 0:
        click_stack.pop()
        if len(click_stack) == 0:
            new_obj = original_selection
        else:
            new_item = click_stack[-1]
            new_obj = new_item['object']

        new_tree = get_object_tree(new_obj)
        return new_tree
