import os
import io

import yaml
import numpy as np
from PIL import Image, ImageDraw, ImageOps

from fpm.utils import load_template, save_file


def generate_occ_grid(model, output_path, **custom_args):
    model = model
    spaces = model.spaces
    wall_openings = model.wall_openings

    resolution = custom_args.get("resolution", 0.05)
    occupied_thresh = custom_args.get("occupied_thresh", 0.65)
    free_thresh = custom_args.get("free_thresh", 0.196)
    negate = custom_args.get("negate", 0)

    unknown = custom_args.get("unknown", 200)
    occupied = custom_args.get("occupied", 0)
    free = custom_args.get("free", 255)
    laser_height = custom_args.get("laser_height", 0.7)
    border = custom_args.get("border", 50)

    if "{{model_name}}" in output_path:
        output_path = output_path.replace("{{model_name}}", model.name)
        if not os.path.exists(output_path):
            os.makedirs(output_path)

    points = []
    directions = []

    for space in spaces:
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

    center = [
        -float(abs(west) + border * resolution / 2),
        -float(abs(south) + border * resolution / 2),
        0,
    ]

    save_map_metadata(
        output_path,
        model,
        resolution,
        center,
        occupied_thresh,
        free_thresh,
        negate,
    )

    # Create canvas
    floor = (
        int(abs(east - west) / resolution) + border,
        int(abs(north - south) / resolution) + border,
    )

    im = Image.new("L", floor, unknown)
    draw = ImageDraw.Draw(im)

    for shape in points:
        shape = get_2d_shape(west, south, resolution, border, shape=shape)
        draw_2d_shape(draw, shape, fill=free)

    for space in spaces:
        for wall in space.walls:
            points, _ = wall.generate_3d_structure()
            shape = get_2d_shape(west, south, resolution, border, points=points)
            draw_2d_shape(draw, shape, fill=occupied)

    for wall_opening in wall_openings:
        shape = wall_opening.generate_2d_structure(laser_height)

        if shape is None:
            continue

        shape = get_2d_shape(west, south, resolution, border, shape=shape)
        draw_2d_shape(draw, shape, fill=free)

    for space in spaces:
        for feature in space.floor_features:
            points, _ = feature.generate_3d_structure()

            if points[int(len(points) / 2) :, 2][0] < laser_height:
                continue

            shape = get_2d_shape(west, south, resolution, border, points=points)
            draw_2d_shape(draw, shape, fill=occupied)

    name_image = "{}.pgm".format(model.name)
    im = ImageOps.flip(im)
    im.save(os.path.join(output_path, name_image), quality=95)


def draw_2d_shape(draw, shape, fill):
    draw.polygon(shape[:, 0:2].flatten().tolist(), fill=fill)


def get_2d_shape(west, south, resolution, border, points=None, shape=None):
    if shape is None:
        shape = points[0 : int(len(points) / 2), 0:2]
    shape[:, 0] = (shape[:, 0] + abs(west)) / resolution
    shape[:, 1] = (shape[:, 1] + abs(south)) / resolution
    shape += border / 2
    shape = shape.astype(int)

    return shape


def save_map_metadata(
    output_path, model, resolution, center, occupied_thresh, free_thresh, negate
):
    file_name = "{}.yaml".format(model.name)
    map_metadata = {
        "resolution": resolution,
        "origin": center,
        "occupied_thresh": occupied_thresh,
        "free_thresh": free_thresh,
        "negate": negate,
        "image": "{}.pgm".format(model.name),
    }

    save_file(output_path, file_name, map_metadata)
