import os
import io

import yaml
import numpy as np
from PIL import Image, ImageDraw, ImageOps

import configparser
from pathlib import Path


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

        self.map_yaml_resolution = config.getfloat("map_yaml", "resolution")
        self.map_yaml_occupied_thresh = config.getfloat("map_yaml", "occupied_thresh")
        self.map_yaml_free_thresh = config.getfloat("map_yaml", "free_thresh")
        self.map_yaml_negate = config.getint("map_yaml", "negate")

        self.map_unknown = config.getint("map", "unknown")
        self.map_occupied = config.getint("map", "occupied")
        self.map_free = config.getint("map", "free")
        self.map_laser_height = config.getfloat("map", "laser_height")
        self.map_output_folder = config["map"]["output_folder"]
        self.map_border = config.getint("map", "border")

        if "{{model_name}}" in self.map_output_folder:
            self.map_output_folder = self.map_output_folder.replace(
                "{{model_name}}", model.name
            )
            if not os.path.exists(self.map_output_folder):
                os.makedirs(self.map_output_folder)

    def model_to_occupancy_grid_transformation(self):

        unknown = self.map_unknown
        occupied = self.map_occupied
        free = self.map_free
        res = self.map_yaml_resolution
        border = self.map_border
        laser_height = self.map_laser_height

        points = []
        directions = []

        for space in self.spaces:
            shape = space.get_shape()
            shape_points = shape.get_points()
            points.append(shape_points)

            directions.append(
                [
                    np.amax(shape_points[:, 1]),  # north
                    np.amin(shape_points[:, 1]),  # south
                    np.amax(shape_points[:, 0]),  # east
                    np.amin(shape_points[:, 0]),  # west
                ]
            )

        directions = np.array(directions)
        north = np.amax(directions[:, 0])
        south = np.amin(directions[:, 1])
        east = np.amax(directions[:, 2])
        west = np.amin(directions[:, 3])

        # Create canvas
        floor = (
            int(abs(east - west) / res) + border,
            int(abs(north - south) / res) + border,
        )

        im = Image.new("L", floor, unknown)
        draw = ImageDraw.Draw(im)

        center = [
            -float(abs(west) + border * res / 2),
            -float(abs(south) + border * res / 2),
            0,
        ]

        for shape in points:
            shape[:, 0] = (shape[:, 0] + abs(west)) / res
            shape[:, 1] = (shape[:, 1] + abs(south)) / res
            shape += border / 2
            shape = shape.astype(int)

            draw.polygon(shape[:, 0:2].flatten().tolist(), fill=free)

        for space in self.spaces:
            for wall in space.walls:
                points, _ = wall.generate_3d_structure()

                shape = points[0 : int(len(points) / 2), 0:2]
                shape[:, 0] = (shape[:, 0] + abs(west)) / res
                shape[:, 1] = (shape[:, 1] + abs(south)) / res
                shape += border / 2
                shape = shape.astype(int)

                draw.polygon(shape[:, 0:2].flatten().tolist(), fill=occupied)

        name_yaml = "{}.yaml".format(self.model.name)
        name_image = "{}.pgm".format(self.model.name)

        with io.open(
            os.path.join(self.map_output_folder, name_yaml), "w", encoding="utf8"
        ) as outfile:
            pgm_config = {
                "resolution": res,
                "origin": center,
                "occupied_thresh": self.map_yaml_occupied_thresh,
                "free_thresh": self.map_yaml_free_thresh,
                "negate": self.map_yaml_negate,
                "image": name_image,
            }
            yaml.dump(pgm_config, outfile, default_flow_style=False, allow_unicode=True)

        for wall_opening in self.wall_openings:

            shape = wall_opening.generate_2d_structure(laser_height)

            if shape is None:
                continue

            shape[:, 0] = (shape[:, 0] + abs(west)) / res
            shape[:, 1] = (shape[:, 1] + abs(south)) / res
            shape += border / 2
            shape = shape.astype(int)

            draw.polygon(shape[:, 0:2].flatten().tolist(), fill=free)

        for space in self.spaces:
            for feature in space.floor_features:
                points, _ = feature.generate_3d_structure()

                if points[int(len(points) / 2) :, 2][0] < laser_height:
                    continue

                shape = points[0 : int(len(points) / 2), 0:2]
                shape[:, 0] = (shape[:, 0] + abs(west)) / res
                shape[:, 1] = (shape[:, 1] + abs(south)) / res
                shape += border / 2
                shape = shape.astype(int)

                draw.polygon(shape[:, 0:2].flatten().tolist(), fill=occupied)

        im = ImageOps.flip(im)
        im.save(os.path.join(self.map_output_folder, name_image), quality=95)
