#!/usr/bin/env python

# SPDX-License-Identifier: LGPL-3.0-or-later
import sys
import os

from rdflib import RDF

from helpers.compute import create_inset_json_ld

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as Pol

from jinja2 import Environment, FileSystemLoader

import yaml

from fpm.graph import build_graph_from_directory, prefixed, traverse_to_world_origin
from fpm.constants import FP, POLY, GEOM, COORD, COORD_EXT
from fpm.utils import load_config_file, build_transformation_matrix

if __name__=="__main__":
    
    argv = sys.argv
    input_folder = argv[1]

    # Config
    config = load_config_file('../../../config/setup.toml')

    points_output_path = config["points"]["output"]
    models_output_path = config["models"]["output"]
    worlds_output_path = config["worlds"]["output"]
    launch_output_path = config["launch"]["output"]
    pkg_path_output_path = config["launch"]["pkg_path"]
    inset_width = config["inset"]["width"]

    g = build_graph_from_directory(input_folder)

    floorplan = g.value(predicate=RDF.type, object=FP["FloorPlan"])
    model_name = prefixed(g, floorplan).split('floorplan:')[1]

    spaces = []
    space_ptr = g.value(floorplan, FP["spaces"])
    # Go through the list of spaces
    while True:
        spaces.append(g.value(space_ptr, RDF.first))
        space_ptr = g.value(space_ptr, RDF.rest)
        if space_ptr == RDF.nil:
                break

    # for each space, find the polygon
    space_points = []
    for space in spaces:
        point_nodes = []
        polygon = g.value(space, FP["shape"])

        point_ptr = g.value(polygon, POLY["points"])

        while True:
            point_nodes.append(g.value(point_ptr, RDF.first))
            point_ptr = g.value(point_ptr, RDF.rest)
            if point_ptr == RDF.nil:
                break
        
        positions = []
        for point in point_nodes:

            position = g.value(predicate=GEOM["of"], object=point)
            coordinates = g.value(predicate=COORD["of-position"], object=position)

            x = g.value(coordinates, COORD["x"]).toPython()
            y = g.value(coordinates, COORD["y"]).toPython()
            asb = g.value(coordinates, COORD["as-seen-by"])

            position = {
                "x": x,
                "y": y,
                "as-seen-by": prefixed(g, asb)
            }
            positions.append(position)
        space_points_json = {
            "name": prefixed(g, space),
            "points": positions
        }
        space_points.append(space_points_json)

    print("creating the insets...")
    inset_model_framed = create_inset_json_ld(space_points, inset_width, input_folder)
   
    print("calculating transformation path...")
    coordinates_map = {}

    for coord, _, _ in g.triples((None, RDF.type, COORD["PoseCoordinate"])):
        coordinates_map[prefixed(g, g.value(coord, COORD["of-pose"]))] = {
            'x' : g.value(coord, COORD["x"]).toPython(),
            'y' : g.value(coord, COORD["y"]).toPython(),
            'theta' : g.value(coord, COORD_EXT["theta"]).toPython()
        }
    
    insets = []
    plt.axis('equal') 
    ax = plt.gca()

    print("transforming the insets")
    for inset in inset_model_framed:

        inset_points = []

        for point in inset["fp:points"]:
            frame = point["as-seen-by"]
            name = point["name"][27:-6]
            point_name = point["name"][15:22]
            name = "{}-{}".format(name, point_name)
            path = traverse_to_world_origin(g, frame)

            path_positions = [str(prefixed(g, p)) for p in path]
            path_positions = [p for p in path_positions if 'pose' in p]
            
            p = np.array([[point["x"]], [point["y"]], [0], [1]]).astype(float)

            path_positions = path_positions[::-1]
            path_positions.append(0)
            for pose, next_pose in zip(path_positions[:-1], path_positions[1:]):
                
                coordinates = coordinates_map[pose]
                T = build_transformation_matrix(coordinates['x'], coordinates['y'], coordinates['theta']).astype(float)
                if not next_pose == 0:
                    if next_pose.count('wall') > 1:
                        T = np.linalg.pinv(T)

                p = np.dot(T, p)

            #inset_points.append([round(p[0, 0].item(), 2), round(p[1, 0].item(), 2), 0])
            x = round(p[0, 0].item(), 2)
            y = round(p[1, 0].item(), 2)
    
            inset_points.append({"id":name, "x":x, "y":y, "z":0, "yaw":0})

        
        insets.append({
            "name" : inset["name"],
            "waypoints" : inset_points
        })

        inset_points = np.array([np.array([i["x"], i["y"]]) for i in inset_points])
        ax.scatter(inset_points[:, 0], inset_points[:, 1])
        ax.add_patch(Pol(inset_points, closed=True, edgecolor='g', fill=False))


    plt.xlim([-30, 30])
    plt.ylim([-30, 30])

    # plt.show()

    print("wrinting all outputs...")
    # Write points to yaml file

    directory = os.path.join(points_output_path, model_name)
    if not os.path.exists(directory):
        os.makedirs(directory)

    for inset in insets:
        name = inset["name"]
        yaml_json = {
            "task" : [{
                "name" : name,
                "waypoints": inset["waypoints"],
                "type":"waypoint_following"
            }]
        }

        with open(os.path.join(points_output_path, model_name, '{name}_task.yaml'.format(name=name)), 'w') as file:
            documents = yaml.dump(yaml_json, file, default_flow_style=None)

    # Model
    # TODO Remove hardocoded paths!
    file_loader = FileSystemLoader('../../../templates/task_generation')
    env = Environment(loader=file_loader)

    template = env.get_template('model.config.jinja')
    output = template.render(model_name=model_name)

    directory = os.path.join(models_output_path, model_name)
    if not os.path.exists(directory):
        os.makedirs(directory)
    
    with open(os.path.join(directory, "model.config"), "w") as f:
        f.write(output)

    template = env.get_template('model.sdf.jinja')
    output = template.render(model_name=model_name)

    with open(os.path.join(directory, "model.sdf"), "w") as f:
        f.write(output)

    # TODO Folder is not created: Autocreate if it doesn't exists
    template = env.get_template('world.sdf.jinja')
    output = template.render(model_name=model_name)

    with open(os.path.join(worlds_output_path, "{name}.world".format(name=model_name)), "w") as f:
        f.write(output)

    template = env.get_template('gazebo.launch.jinja')
    output = template.render(pkg_path=pkg_path_output_path, world_name=model_name)

    # TODO Folder is not created: Autocreate if it doesn't exists
    with open(os.path.join(launch_output_path, "{name}.launch".format(name=model_name)), "w") as f:
        f.write(output)

    print("done.")