#!/usr/bin/env python

# SPDX-License-Identifier: LGPL-3.0-or-later

import rdflib
import json
from pyld import jsonld
from pprint import pprint

from rdflib import URIRef
from rdflib.namespace import RDF

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as Pol

import yaml



if __name__ == "__main__":

    # 1. Construct the RDF graph
    g = rdflib.Graph()
    g.parse("models/skeleton.json", format="json-ld")
    g.parse("models/spatial_relations.json", format="json-ld")
    g.parse("models/coordinate.json", format="json-ld")
    g.parse("output/insets.json", format="json-ld")

    load = loader("")

    # 2. Run the SPARQL query (graph-to-graph)
    aux = load("queries/inset.rq")
    res = g.query(aux)

    res_json = json.loads(res.serialize(format="json-ld"))
    
    context = [
        "https://comp-rob2b.github.io/metamodels/geometry/structural-entities.json",
        "https://comp-rob2b.github.io/metamodels/geometry/spatial-relations.json",
        "https://comp-rob2b.github.io/metamodels/geometry/coordinates.json",
        "https://comp-rob2b.github.io/metamodels/qudt.json",
        {
            "@base": "http://exsce-floorplan.org/",
            "fp" : "http://exsce-floorplan.org/",
            "xsd": "http://www.w3.org/2001/XMLSchema#",
            "polygon" : "fp:polygon",
            "points": {
                "@id": "fp:points",
                "@container": "@list",
                "@type": "@id"
            },
            "shape" : {
                "@id" : "fp:shape",
                "@type" : "@id"
            }
        }
    ]

    model = { "@graph": res_json, "@context": context }

    # 4. Run PyLD's framing algorithm (graph-to-tree)
    frame = json.loads(load("templates/inset_frame.json"))
    model_framed = jsonld.frame(model, frame)

    with open("output/inset_res_framed.json", "w") as file:
        json.dump(model_framed, file, indent=4)

    with open("output/inset_res_graph.json", "w") as file:
        json.dump(res_json, file, indent=4)
    
    query = str(load("queries/coord.rq"))
    res = g.query(query)
    res_json = json.loads(res.serialize(format="json-ld"))

    context = [{
        "@base": "http://exsce-floorplan.org/",
        "coord" : "https://comp-rob2b.github.io/metamodels/geometry/coordinates#",
        "theta":"coord:theta",
        "of-pose" : {
            "@id" : "coord:of-pose",
            "@type" : "@id"
        },
        "name": "@id",
        "data": "@graph"
    },
    "https://comp-rob2b.github.io/metamodels/geometry/structural-entities.json",
    "https://comp-rob2b.github.io/metamodels/geometry/spatial-relations.json",
    "https://comp-rob2b.github.io/metamodels/geometry/coordinates.json",
    "https://comp-rob2b.github.io/metamodels/qudt.json"
    ]
    model = { "@graph": res_json, "@context": context }

    # 4. Run PyLD's framing algorithm (graph-to-tree)
    frame = json.loads(load("templates/coord_frame.json"))
    coord_model_framed = jsonld.frame(model, frame)

    coordinates_map = {}
    for coord in coord_model_framed['data']:
        coordinates_map[coord['of-pose']] = {
            'x' : coord['x'],
            'y' : coord['y'],
            'theta' : coord['theta']
        }

    insets = []
    for inset in model_framed["data"]:

        inset_points = []
        for point in inset["fp:points"]:
            frame = point["Position"]["as-seen-by"]
            path = traverse_to_world_origin(g, frame)

            path_positions = [str(prefixed(g, p))[3:] for p in path]
            #print(path_positions)
            path_positions = [p for p in path_positions if 'pose' in p]
            #print(path_positions)
            
            p = np.array([[point["Position"]["x"]], [point["Position"]["y"]], [0], [1]]).astype(float)

            path_positions = path_positions[::-1]
            path_positions.append(0)

            for pose, next_pose in zip(path_positions[:-1], path_positions[1:]):
                #print(pose, next_pose)
                coordinates = coordinates_map[pose]
                T = build_transformation_matrix(coordinates['x'], coordinates['y'], coordinates['theta']).astype(float)
                # T =np.linalg.pinv(T)
                if not next_pose == 0:
                    if next_pose.count('wall') > 1:
                        T = np.linalg.pinv(T)
                
                # if pose.count('wall') > 1:
                #         T = np.linalg.pinv(T)

                p = np.dot(T, p)
                #print(pose, T)
            
            inset_points.append([round(p[0, 0].item(), 2), round(p[1, 0].item(), 2), 0])
        
        insets.append({
            "name" : inset["name"][3:],
            "waypoints" : inset_points
        })
    # plt.axis('equal') 
    # ax = plt.gca()
    # inset_points = np.array(inset_points)
    # ax.scatter(inset_points[:, 0], inset_points[:, 1])
    # plt.xlim([-30, 30])
    # plt.ylim([-30, 30])
    # plt.show()

    # Write points to yaml file
    yaml_json = {
        "type" : "waypoint_following",
        "insets" : insets
    }
    with open('output/task.yaml', 'w') as file:
        documents = yaml.dump(yaml_json, file, default_flow_style=None)

    # Write Gazebo world
    # 