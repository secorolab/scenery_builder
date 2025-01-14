#!/usr/bin/env python

# SPDX-License-Identifier: LGPL-3.0-or-later

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as Pol

from fpm.graph import (
    traverse_to_world_origin,
    get_space_points,
    get_coordinates_map,
    get_path_positions,
    get_floorplan_model_name
)
from fpm.utils import build_transformation_matrix
from fpm.constants import FPMODEL

def inset_shape(points, width=0.3):
    lines = []
    for point_a, point_b in zip(points[0:-1], points[1:]):
        dy = point_b[1] - point_a[1]
        dx = point_b[0] - point_a[0]
        if not dx == 0:
            m = dy / dx
            b = point_a[1] - m * point_a[0]
            aux = width * np.sqrt(m**2 + 1)

            b1 = b + aux
            b2 = b - aux

            if abs(b1) < abs(b2):
                lines.append([m, -1, b1])
            else:
                lines.append([m, -1, b2])

        else:
            c = point_a[0]
            c1 = c - width
            c2 = c + width

            if abs(c1) < abs(c2):
                lines.append([1, 0, -c1])
            else:
                lines.append([1, 0, -c2])

    lines.append(lines[0])
    lines = np.array(lines)

    inset = []
    for line_a, line_b in zip(lines[0:-1], lines[1:]):
        cross = np.cross(line_a, line_b)
        x = cross[0] / cross[2]
        y = cross[1] / cross[2]
        inset.append([x, y])

    return np.array(inset)


def create_inset_json_ld(model, width):

    tree_structure = []

    for space in model:

        points = list()
        for point in space["points"]:
            xs = point["x"]
            ys = point["y"]
            points.append([float(xs), float(ys), 0, 1])

        points.append(points[0])
        points = np.array(points)
        inset = inset_shape(points, width)
        space_name = space["name"].split(":")[1]

        # create a coordinate relation per point
        tree_points = []
        for i, point in enumerate(inset):
            point = {
                "name": "position-inset-point-{i}-to-{name}-frame".format(
                    i=i, name=space_name
                ),
                "as-seen-by": "{name}-frame".format(name=space_name),
                "x": point[0],
                "y": point[1],
            }
            tree_points.append(point)

        # create a polygon with all points
        polygon = {"points": tree_points, "name": space_name}
        tree_structure.append(polygon)

    return tree_structure


def get_waypoint_coord(g, point, coordinates_map):
    # Gets the coordinates of a point wrt world frame
    frame = point["as-seen-by"]
    path = traverse_to_world_origin(g, frame)

    path_positions = get_path_positions(g, path)

    p = np.array([[point["x"]], [point["y"]], [0], [1]]).astype(float)

    path_positions = path_positions[::-1]
    path_positions.append(0)
    for pose, next_pose in zip(path_positions[:-1], path_positions[1:]):

        coordinates = coordinates_map[pose]
        T = build_transformation_matrix(
            coordinates["x"], coordinates["y"], 0, coordinates["alpha"]
        ).astype(float)
        if not next_pose == 0:
            if next_pose.count("wall") > 1:
                T = np.linalg.pinv(T)

        p = np.dot(T, p)

    # inset_points.append([round(p[0, 0].item(), 2), round(p[1, 0].item(), 2), 0])
    x = round(p[0, 0].item(), 2)
    y = round(p[1, 0].item(), 2)

    return x, y


def transform_insets(g, inset_model_framed, coordinates_map):
    plt.axis("equal")
    ax = plt.gca()
    insets = []

    for inset in inset_model_framed:

        inset_points = []

        for point in inset["points"]:
            name = point["name"][26:-6]
            point_name = point["name"][15:22]
            name = "{}-{}".format(name, point_name)

            x, y = get_waypoint_coord(g, point, coordinates_map)

            inset_points.append({"id": name, "x": x, "y": y, "z": 0, "yaw": 0})

        yaml_json = {
            "name": inset["name"],
            "waypoints": inset_points,
            "type": "waypoint_following",
        }
        insets.append(yaml_json)

        inset_points = np.array([np.array([i["x"], i["y"]]) for i in inset_points])
        ax.scatter(inset_points[:, 0], inset_points[:, 1])
        ax.add_patch(Pol(inset_points, closed=True, edgecolor="g", fill=False))

    plt.xlim([-30, 30])
    plt.ylim([-30, 30])
    # plt.show()

    return insets


def get_all_disinfection_tasks(g, inset_width):

    model_name = get_floorplan_model_name(g)

    g.bind("fpmodel", FPMODEL["{}/".format(model_name)])
    space_points = get_space_points(g)

    print("Creating the insets...")
    inset_model_framed = create_inset_json_ld(space_points, inset_width)

    print("Calculating transformation path...")
    # This just gets the coordinates of all poses in the graph, it doesn't calculate anything
    coordinates_map = get_coordinates_map(g)

    print("Transforming the insets")
    insets = transform_insets(g, inset_model_framed, coordinates_map)

    return [dict(id=inset["name"], task=[inset]) for inset in insets]
