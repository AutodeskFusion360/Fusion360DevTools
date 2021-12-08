import adsk.core
import adsk.fusion

from ...lib.fusion360utils import app


def add_appearances_to_tree(node_list):
    face_keys = {}
    design = adsk.fusion.Design.cast(app.activeProduct)
    all_appearances = design.appearances

    for appearance in all_appearances:
        used_by = appearance.usedBy

        for item in used_by:
            add_node = True

            appearance_node = {"state": {"checked": True}}

            appearance_name = appearance.name
            appearance_id = appearance.id

            appearance_node["type"] = "1-appearance"
            appearance_node['text'] = appearance_name

            if item.objectType == adsk.fusion.BRepBody.classType():
                body = {
                    'text': item.name,
                    "type": "3-body",
                    "state": {"opened": True,
                              "checkbox_disabled": True
                              }
                }

                if item.assemblyContext is not None:
                    body['parent'] = item.assemblyContext.name
                    body['id'] = item.assemblyContext.fullPathName + " - " + item.name

                else:
                    body['parent'] = design.rootComponent.name
                    body['id'] = design.rootComponent.name + " - " + item.name

                appearance_node['parent'] = body['id']
                appearance_node['id'] = body['id'] + " - " + appearance_name

                # Check if source is material or appearance
                if item.appearanceSourceType == adsk.core.AppearanceSourceTypes.MaterialAppearanceSource:
                    if item.material.id != app.preferences.materialPreferences.defaultMaterial.id:
                        appearance_id = item.material.id
                        appearance_node["type"] = "2-material"
                    else:
                        add_node = False

                # If not a material add a node for material if it is not the default
                else:
                    if item.material.id != app.preferences.materialPreferences.defaultMaterial.id:
                        appearance_node_2 = {
                            "state": {"checked": True},
                            "type": "2-material",
                            'text': item.material.name,
                            "parent": body['id'],
                            "id": body['id'] + " - " + item.material.name
                        }
                        item.attributes.add("AppearanceUtilitiesPalette", appearance_node_2['id'], item.material.id)
                        node_list.append(appearance_node_2)

                if not face_keys.get(body['id'], False):
                    node_list.append(body)
                    face_keys[body['id']] = True

            elif item.objectType == adsk.fusion.BRepFace.classType():

                body = {
                    'text': item.body.name,
                    "type": "3-body",
                    "state": {"opened": False,
                              "checkbox_disabled": True}
                }

                face = {
                    'text': "Face" + " - " + str(item.tempId),
                    "type": "5-face",
                    "state": {"opened": True,
                              "checkbox_disabled": True}
                }

                if item.assemblyContext is not None:
                    body['parent'] = item.assemblyContext.name
                    face['parent'] = item.assemblyContext.fullPathName + " - " + item.body.name
                    appearance_node['parent'] = item.assemblyContext.fullPathName + " - " + str(item.tempId)
                    body['id'] = item.assemblyContext.fullPathName + " - " + item.body.name
                    face['id'] = item.assemblyContext.fullPathName + " - " + str(item.tempId)
                    appearance_node['id'] = face['id'] + " - " + appearance_name

                else:
                    body['parent'] = design.rootComponent.name
                    face['parent'] = design.rootComponent.name + " - " + item.body.name
                    appearance_node['parent'] = design.rootComponent.name + " - " + str(item.tempId)
                    body['id'] = design.rootComponent.name + " - " + item.body.name
                    face['id'] = design.rootComponent.name + " - " + str(item.tempId)
                    appearance_node['id'] = face['id'] + " - " + appearance_name

                if not face_keys.get(body['id'], False):
                    node_list.append(body)
                    face_keys[body['id']] = True

                node_list.append(face)

            elif item.objectType == adsk.fusion.Occurrence.classType():
                appearance_node['id'] = item.name + " - " + appearance_name
                appearance_node['parent'] = item.name

            elif item.objectType == adsk.fusion.Component.classType():
                appearance_node['id'] = item.name + " - " + appearance_name
                appearance_node['parent'] = item.name
                appearance_node["state"] = {"checkbox_disabled": True,
                                            "checked": True
                                            }
                appearance_node["type"] = "1-root_appearance"

            else:
                return

            if add_node:
                item.attributes.add("AppearanceUtilitiesPalette", appearance_node['id'], appearance_id)
                node_list.append(appearance_node)


def make_component_tree():
    node_list = []
    design = adsk.fusion.Design.cast(app.activeProduct)

    root_node = {
        'id': design.rootComponent.name,
        'text': design.rootComponent.name,
        "type": "4-root_component",
        'parent': "#",
        "state": {"opened": True,
                  "checkbox_disabled": True
                  }

    }
    node_list.append(root_node)

    if design.rootComponent.occurrences.count > 0:
        make_assembly_nodes(design.rootComponent.occurrences, node_list, design.rootComponent.name)

    return node_list


def make_assembly_nodes(occurrences: adsk.fusion.OccurrenceList, node_list, parent):
    for occurrence in occurrences:

        node = {
            'id': occurrence.name,
            'text': occurrence.name,
            'parent': parent,
            "state": {"opened": False,
                      "checkbox_disabled": True
                      }
        }

        if occurrence.childOccurrences.count > 0:

            node["type"] = "4-component_group"
            node_list.append(node)
            make_assembly_nodes(occurrence.childOccurrences, node_list, occurrence.name)

        else:
            node["type"] = "4-component"
            node_list.append(node)


def adjust_material(node_id, appearance_checked, node_type):
    design = adsk.fusion.Design.cast(app.activeProduct)
    attributes = design.findAttributes("AppearanceUtilitiesPalette", node_id)

    if len(attributes) > 0:
        item = attributes[0].parent

        if item is not None:
            if not appearance_checked:

                if node_type == "2-material":
                    item.material = app.preferences.materialPreferences.defaultMaterial
                else:
                    item.appearance = None
            else:
                if node_type == "2-material":
                    item.material = design.materials.itemById(attributes[0].value)
                else:
                    item.appearance = design.appearances.itemById(attributes[0].value)


def build_data():
    node_list = make_component_tree()
    add_appearances_to_tree(node_list)

    return {'core': node_list, 'root_name': "the_root"}
