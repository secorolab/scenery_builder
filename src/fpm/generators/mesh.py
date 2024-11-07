import os

import bpy
import configparser
from pathlib import Path

from fpm.transformations.blender import (
    boolean_operation_difference,
    clear_scene,
    create_mesh,
    create_collection,
    export,
)


class FloorPlan(object):
    """
    Floor plan model interpreter
    """

    def __init__(self, model):
        # instanciate all walls (boundary lines for each space)
        self.model = model
        self.spaces = model.spaces
        self.wall_openings = model.wall_openings

        # config file
        config = configparser.ConfigParser()
        path_to_file = Path(
            os.path.dirname(os.path.abspath(__file__))
        ).parent.parent.parent
        config.read(os.path.join(path_to_file, "config", "setup.cfg"))

        self.output_3d_file = config["model"]["output_folder"]
        self.format_3d_file = config["model"]["format"]

        if "{{model_name}}" in self.output_3d_file:
            self.output_3d_file = self.output_3d_file.replace(
                "{{model_name}}", model.name
            )
            print(self.output_3d_file)
            if not os.path.exists(self.output_3d_file):
                os.makedirs(self.output_3d_file)

    def model_to_3d_transformation(self):

        building = create_collection(self.model.name)
        # clear the blender scene
        clear_scene()

        # create wall spaces
        for space in self.spaces:
            for i, wall in enumerate(space.walls):
                vertices, faces = wall.generate_3d_structure()
                create_mesh(building, wall.name, vertices, faces)

            for feature in space.floor_features:
                vertices, faces = feature.generate_3d_structure()
                create_mesh(building, feature.name, vertices, faces)

        # create wall openings
        for wall_opening in self.wall_openings:

            vertices, faces = wall_opening.generate_3d_structure()
            create_mesh(building, wall_opening.name, vertices, faces)

            # boolean operation for walls and opening
            boolean_operation_difference(wall_opening.wall_a.name, wall_opening.name)
            if not wall_opening.wall_b is None:
                boolean_operation_difference(
                    wall_opening.wall_b.name, wall_opening.name
                )

            bpy.data.objects[wall_opening.name].select_set(True)
            bpy.ops.object.delete()

        export(self.format_3d_file, self.output_3d_file, self.model.name)
