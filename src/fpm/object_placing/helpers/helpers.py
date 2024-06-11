import numpy as np
from fpm.constants import *
from rdflib import RDF

from . import traversal

def loader(directory):
    import os
    def load(file):
        with open(os.path.join(directory, file)) as f:
            return f.read()
        return ""
    return load

def prefixed(g, node):
    return node.n3(g.namespace_manager)

def build_transformation_matrix(x, y, z, theta):
    
    c = np.cos 
    s = np.sin

    t = np.array([[x], [y], [z], [1]])
    R = np.array([
        [c(theta), -s(theta), 0],
        [s(theta), c(theta), 0],
        [0, 0, 1],
        [0, 0, 0]]
    )

    return np.hstack((R, t))

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
        # print(current_frame_coordinates)
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

        # print(np.rad2deg(t))
        # Build the transformation matrix
        new_T = build_transformation_matrix(x, y, z, t)

        # If the pose is defined by two wall frames, then invert the transformation matrix
        # This is necessary as the FloorPlan DSL calculate certain transformations using frames from walls
        if prefixed(g, pose).count("wall") > 1:
            # print("HERE ", current_frame_coordinates)
            new_T = np.linalg.pinv(new_T)
        
        # Apply the transform
        T =  np.dot(new_T, T)
    
    return T