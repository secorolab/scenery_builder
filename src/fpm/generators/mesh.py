import bpy

from fpm.transformations.blender import (
    boolean_operation_difference,
    clear_scene,
    create_mesh,
    create_collection,
)
from fpm.graph import get_floorplan_model_name
from fpm.utils import save_file


def generate_3d_mesh(g, output_path, **custom_args):
    file_format = custom_args.get("format", "stl")

    model_name = get_floorplan_model_name(g)

    building = create_collection(model_name)
    # clear the blender scene
    clear_scene()

    spaces = model.spaces
    # create wall spaces
    for space in spaces:
        for i, wall in enumerate(space.walls):
            vertices, faces = wall.generate_3d_structure()
            create_mesh(building, wall.name, vertices, faces)

        for feature in space.floor_features:
            vertices, faces = feature.generate_3d_structure()
            create_mesh(building, feature.name, vertices, faces)

    wall_openings = model.wall_openings
    # create wall openings
    for wall_opening in wall_openings:

        vertices, faces = wall_opening.generate_3d_structure()
        create_mesh(building, wall_opening.name, vertices, faces)

        # boolean operation for walls and opening
        boolean_operation_difference(wall_opening.wall_a.name, wall_opening.name)
        if not wall_opening.wall_b is None:
            boolean_operation_difference(wall_opening.wall_b.name, wall_opening.name)

        bpy.data.objects[wall_opening.name].select_set(True)
        bpy.ops.object.delete()

    file_name = "{name}.{ext}".format(name=model_name, ext=file_format)
    save_file(output_path, file_name, None)
