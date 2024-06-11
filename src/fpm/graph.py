import os
import glob

import numpy as np

import rdflib
from rdflib import RDF

from fpm import traversal
from fpm.constants import GEO, GEOM, COORD, COORD_EXT, QUDT, QUDT_VOCAB, FP
from fpm.utils import build_transformation_matrix

def build_graph_from_directory(input_folder):
    # Build the graph by reading all composable models in the input folder
    g = rdflib.Graph()
    input_models = glob.glob(os.path.join(input_folder, "*.json"))
    for file_path in input_models:
        g.parse(file_path, format="json-ld")

    return g

def prefixed(g, node):
    """Return a Notation-3 (N3) prefixed namespace
    """
    return node.n3(g.namespace_manager)

def get_floorplan_model_name(g):
    floorplan = g.value(predicate=RDF.type, object=FP["FloorPlan"])
    model_name = prefixed(g, floorplan).split('floorplan:')[1]

    return model_name

def traverse_to_world_origin(g, frame):

    # Go through the geometric relation predicates
    pred_filter = traversal.filter_by_predicates([
        GEOM["with-respect-to"],
        GEOM["of"]
    ])
    # Algorithm to traverse the graph
    open_set = traversal.BreadthFirst

    # Set beginning and end point 
    root = GEO[frame[3:]]
    goal = GEO["world-frame"]

    # Set map of visited nodes for path building
    parent_map = {}

    # Traverse the graph
    t_np = traversal.traverse_nodes_with_parent(open_set, g, root, pred_filter)
    for node, parent in ((node, parent) for (node, parent) in t_np if parent):
        parent_map[node] = parent
        if node == goal:
            break
    # Build the path
    path = []
    curr = goal
    while (curr != root):
        path.append(curr)
        curr = parent_map[curr]
    else:
        path.append(root)

    return path


def get_transformation_matrix_wrt_frame(g, root, target):

    # Configure the traversal algorithm
    filter = [
        GEOM["with-respect-to"],
        GEOM["of"]
        ]
    pred_filter = traversal.filter_by_predicates(filter)
    open_set = traversal.BreadthFirst

    # Traverse the graph
    t_nep = traversal.traverse_nodes_with_parent(open_set, g, root, pred_filter)

    # Build the tree
    pose_frame_node_tree = {}

    for node, parent in ((node, parent) for (node, parent) in t_nep if parent):
        pose_frame_node_tree[node] = parent
        if node == target:
            break

    # Get the path from the frame to transform to the target frame
    poses_path = []
    current_node = target
    while (current_node != root):
        # If the node is a frame, do not append to the path
        if not GEO["Frame"] in g.objects(current_node, RDF.type):
            poses_path.append(current_node)
        current_node = pose_frame_node_tree[current_node]

    # Calculate and operate the transformation matrices
    T = np.eye(4)
    for pose in poses_path[::-1]:
        # Get the coordinates for the pose
        current_frame_coordinates = g.value(predicate=COORD["of-pose"], object=pose)

        # Get x and y values
        x = g.value(current_frame_coordinates, COORD["x"]).toPython()
        y = g.value(current_frame_coordinates, COORD["y"]).toPython()

        # If the pose is defined with a VectorXYZ, read the z value, otherwise the value is 0
        z_value = g.value(current_frame_coordinates, COORD["z"])
        z = 0 if z_value == None else z_value.toPython()

        # Read the theta value, if the values is in degrees, transform to radians
        t = g.value(current_frame_coordinates, COORD_EXT["theta"]).toPython()
        if QUDT_VOCAB["degrees"] in g.objects(current_frame_coordinates, QUDT["unit"]):
            t = np.deg2rad(t)

        # Build the transformation matrix
        new_T = build_transformation_matrix(x, y, z, t)

        # If the pose is defined by two wall frames, then invert the transformation matrix
        # This is necessary as the FloorPlan DSL calculate certain transformations using frames from walls
        if prefixed(g, pose).count("wall") > 1:
            new_T = np.linalg.pinv(new_T)

        # Apply the transform
        T =  np.dot(new_T, T)

    return T
