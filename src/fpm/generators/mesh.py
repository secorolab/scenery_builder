import os

import bpy

from fpm.transformations.blender import (
    boolean_operation_difference,
    clear_scene,
    create_mesh,
    create_collection,
    export_blender_scene,
)


def generate_3d_mesh(model, output_path, **custom_args):
    file_format = custom_args.get("format", "stl")

    if "{{model_name}}" in output_path:
        output_path = output_path.replace("{{model_name}}", model.name)
        print(output_path)
        if not os.path.exists(output_path):
            os.makedirs(output_path)

    spaces = model.spaces
    wall_openings = model.wall_openings

    building = create_collection(model.name)
    # clear the blender scene
    clear_scene()

    # create wall spaces
    for space in spaces:
        for i, wall in enumerate(space.walls):
            vertices, faces = wall.generate_3d_structure()
            create_mesh(building, wall.name, vertices, faces)

        for feature in space.floor_features:
            vertices, faces = feature.generate_3d_structure()
            create_mesh(building, feature.name, vertices, faces)

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

    export_blender_scene(output_path, model.name, mesh_format=file_format)
