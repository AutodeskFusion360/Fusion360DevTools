import sys
from collections import defaultdict

import adsk.core
import adsk.fusion
import adsk.cam

from ...lib.fusion360utils import app, ui


def _get_name_type(selection):
    try:
        selection_type = selection.objectType
    except:
        selection_type = "could not determine type"

    try:
        name = selection.name
    except:
        name = "Object has no name"

    return name, selection_type


def _make_attributes_message(attributes, filter_by_group, filter_group_name):
    attribute_list = []

    for attribute in attributes:
        try:
            if filter_by_group:
                if filter_group_name != attribute.groupName:
                    return attribute_list
            attribute_list.append(f"    {attribute.groupName}, {attribute.name}, {attribute.value} \n")
        except:
            attribute_list.append("some failure")

    return attribute_list


def attributes_for_selection(selection, filter_by_group, filter_group_name) -> list:
    msg_list = []

    name, the_selection_type = _get_name_type(selection)

    msg_list.append("Object Type:  {} \n".format(the_selection_type))
    msg_list.append("Object Name:  {} \n".format(name))
    try:
        attributes = selection.attributes
        if len(attributes) == 0:
            msg_list.append("   There are no attributes")
        attribute_list = _make_attributes_message(attributes, filter_by_group, filter_group_name)
        if len(attribute_list) > 0:
            msg_list.extend(attribute_list)
    except:
        msg_list.append("    Selected Object Type Does not support attributes")

    return msg_list


def get_all_attributes(attribute_group: str, attribute_name: str) -> list:
    msg_list = []
    design = adsk.fusion.Design.cast(app.activeProduct)
    attributes = design.findAttributes(attribute_group, attribute_name)

    if len(attributes) > 0:
        unique_objects = defaultdict(list)
        orphans = []

        for attribute in attributes:
            if attribute.parent is not None:
                entity_token = attribute.parent.entityToken
                unique_objects[entity_token].append(attribute)
            else:
                orphans.append(attribute)

        for key, object_attributes in unique_objects.items():
            name, the_selection_type = _get_name_type(object_attributes[0].parent)
            attribute_list = _make_attributes_message(object_attributes, False, '')

            if len(attribute_list) > 0:
                msg_list.append("\n ----*********---- \n\n")
                msg_list.append("Object Type:  {} \n".format(the_selection_type))
                msg_list.append("Object Name:  {} \n".format(name))
                msg_list.append("Attributes (Group Name, Attribute Name, Value):\n")
                msg_list.extend(attribute_list)

        if len(orphans) > 0:
            msg_list.append("\n ----*********---- \n\n")
            msg_list.append("Orphans (parent no longer exists):\n")
            msg_list.append("Attributes (Group Name, Attribute Name, Value):\n")
            attribute_list = _make_attributes_message(orphans, False, '')
            if len(attribute_list) > 0:
                msg_list.extend(attribute_list)

    return msg_list


def update_feedback_from_list(feedback: adsk.core.TextBoxCommandInput, msg_list: list):
    msg_length = len(msg_list)
    if msg_length > 0:
        msg = ''.join(msg_list)

        if msg_length > 30:
            num_rows = 30
        else:
            num_rows = msg_length + 2

    else:
        msg = " Could not find any attributes for group and name inputs"
        num_rows = 2

    feedback.numRows = num_rows
    feedback.formattedText = msg

