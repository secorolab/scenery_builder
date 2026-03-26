import logging
import json
import os.path
import subprocess
import tempfile

from fpm.graph import get_floorplan_model_name, get_3d_structure
from fpm.utils import get_output_path

logger = logging.getLogger("floorplan.generators.mesh")
logger.setLevel(logging.DEBUG)


def generate_3d_mesh(g, output_path, include_doors=False, **custom_args):
    file_format = custom_args.get("format", "stl")
    logger.info("Generating 3D mesh in %s format", file_format)

    elements = {}
    model_name = get_floorplan_model_name(g)
    elements["model_name"] = model_name

    logger.debug("Getting 3D structure for walls")
    walls = get_3d_structure(g, "Wall")
    elements["walls"] = walls

    logger.debug("Getting 3D structure for columns")
    columns = get_3d_structure(g, "Column")
    elements["columns"] = columns

    logger.debug("Getting 3D structure for dividers")
    dividers = get_3d_structure(g, "Divider")
    elements["dividers"] = dividers

    if include_doors:
        logger.debug("Getting 3D structure for doors")
        doors = get_3d_structure(g, "Door")
        elements["doors"] = doors

        logger.debug("Getting 3D structure for door linings")
        door_linings = get_3d_structure(g, "DoorLining")
        elements["door_linings"] = door_linings

    logger.debug("Getting 3D structure for entryways")
    entryways = get_3d_structure(g, "Entryway")
    elements["entryways"] = entryways

    logger.debug("Getting 3D structure for windows")
    windows = get_3d_structure(g, "Window")
    elements["windows"] = windows

    output_files = []
    for e in file_format:
        file_name = "{name}.{ext}".format(name=model_name, ext=e)
        elements.setdefault("output_files", []).append((output_path, file_name))
        output_files.append(os.path.join(output_path, file_name))

    run_blender(elements)
    return output_files


def run_blender(elements):
    """
    Runs the blender transformation as a subprocess
    """
    with tempfile.NamedTemporaryFile(suffix=".json") as f:
        print(f.name)
        with open(f.name, "w") as json_file:
            json.dump(elements, json_file)

        curr_path = os.path.dirname(os.path.realpath(__file__))
        blender_script = os.path.join(curr_path, "../transformations/blender.py")
        cmd = [
            "blender",
            "-b",
            "--python",
            os.path.abspath(blender_script),
            "--",
            f.name,
        ]
        result = subprocess.run(cmd)
        result.check_returncode()


def get_3d_mesh(g, base_path, **kwargs):
    output_path = get_output_path(base_path, "3d-mesh")
    return generate_3d_mesh(g, output_path, **kwargs)
