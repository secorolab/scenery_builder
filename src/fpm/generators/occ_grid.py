import os

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from fpm.graph import (
    get_space_points,
    get_coordinates_map,
    get_floorplan_model_name,
    get_wall_points,
    get_opening_points,
    get_waypoint_coord,
)
from fpm.utils import load_template, save_file
from fpm.constants import FPMODEL


def generate_occ_grid(g, output_path, **custom_args):
    map_name = get_floorplan_model_name(g)

    resolution = custom_args.get("map_resolution", 0.05)

    unknown = custom_args.get("map_unknown_value", 200)
    occupied = custom_args.get("map_occupied_value", 0)
    free = custom_args.get("map_free_value", 255)
    laser_height = custom_args.get("map_laser_height", 0.7)
    border = custom_args.get("map_border", 50)

    if "{{model_name}}" in output_path:
        output_path = output_path.replace("{{model_name}}", map_name)
        if not os.path.exists(output_path):
            os.makedirs(output_path)

    points = []
    directions = []

    coords_m = get_coordinates_map(g)
    space_points = get_space_points(g)
    for s in space_points:
        w_coords = list()
        for p in s.get("points"):
            x, y, _ = get_waypoint_coord(g, p, coords_m)
            w_coords.append([x, y, 0, 1])

        w_coords = np.array(w_coords)
        points.append(w_coords)

        # Get the left/right, top/bottom of each space
        directions.append(
            [
                np.amax(w_coords[:, 1]),  # north
                np.amin(w_coords[:, 1]),  # south
                np.amax(w_coords[:, 0]),  # east
                np.amin(w_coords[:, 0]),  # west
            ]
        )

    # Get the left/right, top/bottom of the entire map
    directions = np.array(directions)
    north = np.amax(directions[:, 0])
    south = np.amin(directions[:, 1])
    east = np.amax(directions[:, 2])
    west = np.amin(directions[:, 3])

    # Get center of the map
    center = [
        -float(abs(west) + border * resolution / 2),
        -float(abs(south) + border * resolution / 2),
        0,
    ]

    save_map_metadata(output_path, map_name, center, **custom_args)

    # Create canvas
    floor = (
        int(abs(east - west) / resolution) + border,
        int(abs(north - south) / resolution) + border,
    )

    im = Image.new("L", floor, unknown)
    draw = ImageDraw.Draw(im)

    # Draw free space from floorplan spaces (rooms)
    draw_floorplan_element(points, draw, free, west=west, south=south, **custom_args)

    # Draw obstacles (walls and columns)
    draw_floorplan_obstacle(
        g, "Wall", draw, west, south, occupied, coords_m, **custom_args
    )
    draw_floorplan_obstacle(
        g, "Column", draw, west, south, occupied, coords_m, **custom_args
    )
    draw_floorplan_obstacle(
        g, "Divider", draw, west, south, occupied, coords_m, **custom_args
    )

    # Clear out wall openings; mark them as free space
    draw_floorplan_opening(
        g, "Entryway", draw, west, south, free, coords_m, **custom_args
    )
    # draw_floorplan_opening(g, "Window", draw, west, south, resolution, border, free, coords_m)

    im = ImageOps.flip(im)

    name_image = "{}.pgm".format(map_name)
    save_file(output_path, name_image, im)


def draw_floorplan_obstacle(g, element, draw, west, south, fill, coords_map, **kwargs):
    column_points = get_wall_points(g, element)
    c_points = list()
    for s in column_points:
        c_coords = list()
        for p in s.get("points"):
            x, y, _ = get_waypoint_coord(g, p, coords_map)
            c_coords.append([x, y, 0, 1])

        c_coords = np.array(c_coords)
        c_points.append(c_coords)

    draw_floorplan_element(
        c_points,
        draw,
        fill,
        west=west,
        south=south,
        **kwargs,
    )


def draw_floorplan_opening(g, element, draw, west, south, fill, coords_map, **kwargs):
    opening_points = get_opening_points(g, element)
    resolution = kwargs.get("resolution", 0.05)

    all_points = list()
    for opening in opening_points:
        for face in opening:
            y_vals = [p.get("y") for p in face]
            if np.all(np.array(y_vals) == y_vals[0]):
                continue
            f_coords = list()
            for p in face:
                if p["y"] == 0.0:
                    p["y"] = p["y"] - resolution
                else:
                    p["y"] = p["y"] + resolution
                x, y, _ = get_waypoint_coord(g, p, coords_map)
                f_coords.append([x, y, 0, 1])
            f_coords = np.array(f_coords)
            all_points.append(f_coords)

    draw_floorplan_element(all_points, draw, fill, west=west, south=south, **kwargs)


def draw_floorplan_element(points, draw, fill, **kwargs):
    west = kwargs.get("west")
    south = kwargs.get("south")
    resolution = kwargs.get("map_resolution", 0.05)
    border = kwargs.get("map_border", 50)

    for shape in points:
        element_shape = get_2d_shape(west, south, resolution, border, shape=shape)
        draw_2d_shape(draw, element_shape, fill=fill, **kwargs)


def draw_2d_shape(draw, shape, fill, outline=None, width=1, **kwargs):
    draw.polygon(
        shape[:, 0:2].flatten().tolist(), fill=fill, outline=outline, width=width
    )


def get_2d_shape(west, south, resolution, border, points=None, shape=None):
    if shape is None:
        shape = points[0 : int(len(points) / 2), 0:2]
    shape[:, 0] = (shape[:, 0] + abs(west)) / resolution
    shape[:, 1] = (shape[:, 1] + abs(south)) / resolution
    shape += border / 2
    shape = shape.astype(int)

    return shape


def save_map_metadata(output_path, map_name, center, **custom_args):
    file_name = "{}.yaml".format(map_name)
    negate = custom_args.get("map_negate", 0)
    resolution = custom_args.get("map_resolution", 0.05)
    occupied_thresh = custom_args.get("map_occupied_threshold", 0.65)
    free_thresh = custom_args.get("map_free_threshold", 0.196)
    map_metadata = {
        "resolution": resolution,
        "origin": center,
        "occupied_thresh": occupied_thresh,
        "free_thresh": free_thresh,
        "negate": negate,
        "image": "{}.pgm".format(map_name),
    }

    save_file(output_path, file_name, map_metadata)
