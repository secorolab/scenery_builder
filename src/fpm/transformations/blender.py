import os
import bpy
import bmesh
import logging

logger = logging.getLogger("floorplan.transformations.blender")
logger.setLevel(logging.DEBUG)


def create_mesh(collection, name, vertices, faces):
    """Creates a mesh"""

    me = bpy.data.meshes.new(name)
    me.from_pydata(vertices, [], faces)
    me.update()

    bm = bmesh.new()
    bm.from_mesh(me, face_normals=True)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    # Finish up, write the bmesh back to the mesh
    bm.to_mesh(me)
    bm.free()  # free and prevent further access
    me.update()

    obj = bpy.data.objects.new(name, me)
    collection.objects.link(obj)


def create_collection(name):
    """Creates an object collection"""

    collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(collection)
    return collection


def clear_scene():
    """Clears the scene from all objects (often the default objects: a cube mesh, a light source, and a camera)"""

    for obj in bpy.context.scene.objects:
        obj.select_set(True)
        bpy.ops.object.delete()


def boolean_operation_difference(obj_name, cutter_name):
    """Performs the difference boolean operation"""

    # select the object
    obj = bpy.data.objects[obj_name]
    # configure modifier
    boolean = obj.modifiers.new(name="boolean", type="BOOLEAN")
    boolean.object = bpy.data.objects[cutter_name]
    boolean.operation = "DIFFERENCE"
    boolean.solver = "EXACT"
    # apply modifier
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier="boolean")


def create_element_mesh(building, elements):
    for e in elements:
        name = e.get("name")
        vertices = e.get("vertices")
        faces = e.get("faces")
        create_mesh(building, name, vertices, faces)


def subtract_opening(openings):
    # boolean operation for walls and opening
    for opening in openings:
        name = opening.get("name")
        for wall in opening.get("voids", list()):
            boolean_operation_difference(wall, name)
        bpy.data.objects[name].select_set(True)
        bpy.ops.object.delete()


def main(elements):
    model_name = elements.get("model_name")
    building = create_collection(model_name)
    # clear the blender scene
    clear_scene()

    walls = elements.get("walls", [])
    create_element_mesh(building, walls)

    columns = elements.get("columns", [])
    create_element_mesh(building, columns)

    dividers = elements.get("dividers", [])
    create_element_mesh(building, dividers)

    doors = elements.get("doors", [])
    create_element_mesh(building, doors)

    door_linings = elements.get("door_linings", [])
    create_element_mesh(building, door_linings)

    entryways = elements.get("entryways", [])
    create_element_mesh(building, entryways)
    subtract_opening(entryways)

    windows = elements.get("windows", [])
    create_element_mesh(building, windows)
    subtract_opening(windows)

    output_files = []
    for output_path, file_name in elements.get("output_files", []):
        f = save_file(file_name, output_path)
        output_files.append(f)

    return output_files


def save_file(file_name, output_path):
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    base_name, ext = os.path.splitext(file_name)
    output_file = os.path.abspath(os.path.join(output_path, file_name))

    if ext in [".stl"]:
        bpy.ops.wm.stl_export(filepath=output_file)
    elif ext in [".dae"]:
        bpy.ops.wm.collada_export(filepath=output_file)
    elif ext in [".gltf", ".glb"]:
        bpy.ops.export_scene.gltf(filepath=output_file)

    logger.info(f"Generated {output_file}")
    return output_file


if __name__ == "__main__":
    import json
    import sys

    args = sys.argv
    with open(args[-1], "r") as f:
        elements = json.load(f)

    main(elements)
