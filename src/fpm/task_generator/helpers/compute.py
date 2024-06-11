#!/usr/bin/env python

# SPDX-License-Identifier: LGPL-3.0-or-later

import rdflib
import json
import os
from pyld import jsonld
from pprint import pprint
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as Pol

import numpy as np

def load_json(path):
    with open(path, "r") as file:
        return json.load(file)

def inset_shape(points, width=0.3):
    lines = []
    for point_a, point_b in zip(points[0:-1], points[1:]):
        dy = point_b[1]-point_a[1]
        dx = point_b[0]-point_a[0]
        if not dx == 0:
            m = dy/dx
            b = point_a[1] - m*point_a[0]
            aux = width * np.sqrt(m**2 + 1)

            b1 = b + aux
            b2 = b - aux
            # d1 = abs(b1) / np.sqrt(m**2 + 1)
            # d2 = abs(b2) / np.sqrt(m**2 + 1)

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
        x = cross[0]/cross[2]
        y = cross[1]/cross[2]
        inset.append([x, y])

    return np.array(inset)
    
def create_inset_json_ld(model, width, output):

    inset_graph = []
    tree_structure = []

    for space in model:

        points = []
        for point in space["points"]:
            xs = point["x"]
            ys = point["y"]
            points.append([float(xs), float(ys), 0 , 1])
        
        points.append(points[0])
        points = np.array(points)
        inset = inset_shape(points, width)
        space_name = space["name"][16:]
        # create an Point per point in the inset
        # for i, point in enumerate(inset):
        #     obj = {
        #         "@id" : "inset:point-inset-space-{name}-{i}".format(name=space_name, i=i),
        #         "@type" : "Point"
        #     }
        #     inset_graph.append(obj)
        # create a spatial relation entitiy per point
        # for i, point in enumerate(inset):
        #     #print(space_name[6:])
        #     obj = {
        #         "@id" : "inset:position-inset-point-{i}-to-{name}".format(i=i, name=space_name),
        #         "@type" : "Position",
        #         "of" : "inset:point-inset-space-{name}-{i}".format(name=space_name, i=i),
        #         "with-respect-to" : "geom:point-center-{name}".format(name=space_name)
        #     }
        #     inset_graph.append(obj)
        
        # create a coordinate relation per point
        tree_points = []
        for i, point in enumerate(inset):
            #print(space_name[6:])
            # obj = {
            #     "@id" : "coord-position-inset-point-{i}-to-{name}-frame".format(name=space_name, i=i),
            #     "@type" : ["PositionReference", "PositionCoordinate","VectorXY"],
            #     "of-position" : "position-inset-point-{i}-to-{name}-frame".format(i=i, name=space_name),
            #     "with-respect-to": "point-center-{name}".format(name=space_name),
            #     "as-seen-by" : point["as-seen-by"],
            #     "unit": "M",
            #     "x": point[0],
            #     "y": point[1]
            # }

            point = {
                "name" : "position-inset-point-{i}-to-{name}-frame".format(i=i, name=space_name),
                "as-seen-by" : "fp:frame-center-{name}".format(name=space_name),
                "x": point[0],
                "y": point[1]
            }
            tree_points.append(point)
            # inset_graph.append(obj) 
        # create a polygon with all points 
        # polygon = ["point-inset-space-{name}-{i}".format(name=space_name, i=i) for i, _ in enumerate(inset)]
        # obj = {
        #     "@id" : "inset:inset-polygon-{name}".format(name=space_name),
        #     "@type" : "Polygon",
        #     "points" : polygon
        # }
        polygon = {
            "fp:points" : tree_points,
            "name" : space_name
        }
        tree_structure.append(polygon)
    
        # inset_graph.append(obj)

    # context = [
    #     "https://raw.githubusercontent.com/opengeospatial/ogc-geosparql/master/1.1/contexts/sf-context.json",
    #     "https://comp-rob2b.github.io/metamodels/geometry/structural-entities.json",
    #     "https://comp-rob2b.github.io/metamodels/geometry/spatial-relations.json",
    #     "https://comp-rob2b.github.io/metamodels/geometry/coordinates.json",
    #     "https://comp-rob2b.github.io/metamodels/qudt.json",
    #     "https://hbrs-sesame.github.io/metamodels/floor-plan/floor-plan.json"
    #     {
    #         "inset": "https://comp-rob2b.github.io/insets#",
    #         "geom": "https://comp-rob2b.github.io/metamodels/geometry/structural-entities#"
    #     }
    # ]

    # inset_json_ld = {
    #     "@context" : context,
    #     "@graph" : inset_graph,
    # }

    # with open(os.path.join(output, "insets.json"), "w") as file:
    #     json.dump(inset_json_ld, file, indent=4)
    
    return tree_structure