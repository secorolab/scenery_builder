import bpy

from fpm.transformations.blender import (
    boolean_operation_difference,
    clear_scene,
    create_mesh,
    create_collection,
)
from fpm.graph import get_floorplan_model_name, get_3d_structure
from fpm.utils import save_file


def generate_3d_mesh(g, output_path, **custom_args):
    file_format = custom_args.get("format", "stl")

    model_name = get_floorplan_model_name(g)

    building = create_collection(model_name)
    # clear the blender scene
    clear_scene()

    print("Getting 3D structures")
    elements = get_3d_structure(g, "Wall")
    create_element_mesh(building, elements)

    columns = get_3d_structure(g, "Column")
    create_element_mesh(building, columns)

    dividers = get_3d_structure(g, "Divider")
    create_element_mesh(building, dividers)

    entryways = get_3d_structure(g, "Entryway")
    create_element_mesh(building, entryways)
    subtract_opening(entryways)

    windows = get_3d_structure(g, "Window")
    create_element_mesh(building, windows)
    subtract_opening(windows)

    file_name = "{name}.{ext}".format(name=model_name, ext=file_format)
    save_file(output_path, file_name, None)


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
