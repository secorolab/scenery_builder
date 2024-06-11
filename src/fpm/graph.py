import os
import glob

import rdflib

from fpm import traversal
from fpm.constants import GEO, GEOM

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
