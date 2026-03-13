import logging
import bpy

from fpm.transformations.blender import (
    boolean_operation_difference,
    clear_scene,
    create_mesh,
    create_collection,
)
from fpm.graph import get_floorplan_model_name, get_3d_structure
from fpm.utils import save_file, get_output_path

logger = logging.getLogger("floorplan.generators.mesh")
logger.setLevel(logging.DEBUG)


def generate_3d_mesh(g, output_path, include_doors=False, **custom_args):
    file_format = custom_args.get("format", "stl")
    logger.info("Generating 3D mesh in %s format", file_format)

    model_name = get_floorplan_model_name(g)

    building = create_collection(model_name)
    # clear the blender scene
    clear_scene()

    logger.debug("Getting 3D structure for walls")
    elements = get_3d_structure(g, "Wall")
    create_element_mesh(building, elements)

    logger.debug("Getting 3D structure for columns")
    columns = get_3d_structure(g, "Column")
    create_element_mesh(building, columns)

    logger.debug("Getting 3D structure for dividers")
    dividers = get_3d_structure(g, "Divider")
    create_element_mesh(building, dividers)

    if include_doors:
        logger.debug("Getting 3D structure for doors")
        doors = get_3d_structure(g, "Door")
        create_element_mesh(building, doors)

        logger.debug("Getting 3D structure for door linings")
        door_linings = get_3d_structure(g, "DoorLining")
        create_element_mesh(building, door_linings)

    logger.debug("Getting 3D structure for entryways")
    entryways = get_3d_structure(g, "Entryway")
    create_element_mesh(building, entryways)
    subtract_opening(entryways)

    logger.debug("Getting 3D structure for windows")
    windows = get_3d_structure(g, "Window")
    create_element_mesh(building, windows)
    subtract_opening(windows)

    output_files = []
    for e in file_format:
        file_name = "{name}.{ext}".format(name=model_name, ext=e)
        output_file = save_file(output_path, file_name, None)
        output_files.append(output_file)
    return output_files


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
            try:
                boolean_operation_difference(wall, name)
            except KeyError as e:
                logger.error(e)
        bpy.data.objects[name].select_set(True)
        bpy.ops.object.delete()


def get_3d_mesh(g, base_path, **kwargs):
    output_path = get_output_path(base_path, "3d-mesh")
    return generate_3d_mesh(g, output_path, **kwargs)
