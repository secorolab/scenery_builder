import os
import glob

import numpy as np

import rdflib
from rdflib import RDF

from fpm import traversal
from fpm.constants import (
    GEO,
    GEOM,
    COORD,
    QUDT,
    QUDT_VOCAB,
    FP,
    POLY,
    FPMODEL,
)
from fpm.utils import build_transformation_matrix


def build_graph_from_directory(inputs: tuple, debug=False):
    # Build the graph by reading all composable models in the input folder
    g = rdflib.Graph()
    for input_folder in inputs:
        input_models = glob.glob(os.path.join(input_folder, "*.json"))
        print("Found {} models in {}".format(len(input_models), input_folder))
        print("Adding to the graph...")
        for file_path in input_models:
            print("\t{}".format(file_path))
            g.parse(file_path, format="json-ld")

    if debug:
        from rdflib.tools.rdf2dot import rdf2dot

        with open("floorplan.dot", "w+") as dotfile:
            rdf2dot(g, dotfile)

        g.serialize("floorplan.json", format="json-ld", auto_compact=True)

    return g


def prefixed(g, node):
    """Return a Notation-3 (N3) prefixed namespace"""
    return node.n3(g.namespace_manager)


def get_list_values(g: Graph, subject, predicate):
    ptr = g.value(subject, predicate)
    values = get_list_from_ptr(g, ptr)
    return values


def get_list_from_ptr(g, ptr):
    result_list = []
    while True:
        result_list.append(g.value(ptr, RDF.first))
        ptr = g.value(ptr, RDF.rest)
        if ptr == RDF.nil:
            break

    return result_list


def get_point_position(g, point):
    position = g.value(predicate=GEOM["of"], object=point)
    coordinates = g.value(predicate=COORD["of-position"], object=position)

    if g.value(coordinates, COORD["coordinates"]):
        coord_values = get_list_values(g, coordinates, COORD["coordinates"])
        if len(coord_values) == 2:
            z = 0.0
            x, y = coord_values
        else:
            x, y, z = coord_values
    else:
        x = get_coord_value(g, coordinates, "x", default=0.0)
        y = get_coord_value(g, coordinates, "y", default=0.0)
        z = get_coord_value(g, coordinates, "z", default=0.0)
    asb = g.value(coordinates, COORD["as-seen-by"])
    name = prefixed(g, coordinates)

    return {
        "name": name,
        "x": float(x),
        "y": float(y),
        "z": float(z),
        "as-seen-by": prefixed(g, asb),
    }


def get_floorplan_model_name(g):
    floorplan = g.value(predicate=RDF.type, object=FP["FloorPlan"])
    if floorplan is None:
        raise ValueError("No FloorPlan found.")
    model_name = prefixed(g, floorplan).split(":")[1]

    return model_name


def traverse_to_world_origin(g, frame):
    # Go through the geometric relation predicates
    pred_filter = traversal.filter_by_predicates([GEOM["with-respect-to"], GEOM["of"]])
    # Algorithm to traverse the graph
    open_set = traversal.BreadthFirst

    # Set beginning and end point
    if "fpm:" in frame:
        root = g.namespace_manager.expand_curie(frame)
    else:
        root = g.namespace_manager.expand_curie("fpm:{}".format(frame))
    goal = g.namespace_manager.expand_curie("fpm:world-frame")

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
    while curr != root:
        path.append(curr)
        curr = parent_map[curr]
    else:
        path.append(root)

    return path


def get_transformation_matrix_wrt_frame(g, root, target):
    # Configure the traversal algorithm
    f = [GEOM["with-respect-to"], GEOM["of"]]
    pred_filter = traversal.filter_by_predicates(f)
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
    while current_node != root:
        # If the node is a frame, do not append to the path
        if not GEO["Frame"] in g.objects(current_node, RDF.type):
            poses_path.append(current_node)
        current_node = pose_frame_node_tree[current_node]

    # Calculate and operate the transformation matrices
    T = np.eye(4)
    for pose in poses_path[::-1]:
        # Get the coordinates for the pose
        current_frame_coordinates = g.value(predicate=COORD["of-pose"], object=pose)

        coordinates = get_coordinates(g, current_frame_coordinates)
        # Get x and y values
        x = coordinates.get("x")
        y = coordinates.get("y")

        # If the pose is defined with a VectorXYZ, read the z value, otherwise the value is 0
        z = coordinates.get("z")

        # Read the theta value, if the values is in degrees, transform to radians
        t = coordinates.get("alpha")
        if QUDT_VOCAB["DEG"] in g.objects(current_frame_coordinates, QUDT["unit"]):
            t = np.deg2rad(t)

        # Build the transformation matrix
        new_T = build_transformation_matrix(x, y, z, t)

        # If the pose is defined by two wall frames, then invert the transformation matrix
        # This is necessary as the FloorPlan DSL calculate certain transformations using frames from walls
        # TODO this works for models generated from the DSL but makes assumptions about IDs, needs a generalized solution
        if prefixed(g, pose).count("wall") > 1:
            new_T = np.linalg.pinv(new_T)

        # Apply the transform
        T = np.dot(new_T, T)

    return T


def get_space_points(g):
    floorplan = g.value(predicate=RDF.type, object=FP["FloorPlan"])

    # Get the list of spaces
    print("Querying all spaces...")
    spaces = get_list_values(g, floorplan, FP["spaces"])

    # for each space, find the polygon
    print("Get all points of a space...")
    space_points = []
    for space in spaces:
        space_points_json = get_point_positions_in_space(g, space)
        space_points.append(space_points_json)

    return space_points


def get_element_points(g, element_type="Wall"):
    print("Querying all {}s...".format(element_type))
    element_points = list()
    for element, _, _ in g.triples((None, RDF.type, FP[element_type])):
        element_points_json = get_point_positions_in_space(g, element)
        element_points_json["height"] = g.value(element, FP["height"]).toPython()
        element_points.append(element_points_json)

    return element_points


def get_opening_points(g, element="Entryway"):
    print("Querying all {}s...".format(element))
    opening_points = list()
    for opening, _, _ in g.triples((None, RDF.type, FP[element])):
        poly = g.value(opening, FP["3d-shape"])
        faces_nodes = get_list_values(g, poly, POLY["faces"])
        face_positions = list()
        for f in faces_nodes:
            face_vertices = get_list_from_ptr(g, f)
            positions = list()
            for point in face_vertices:
                p = get_point_position(g, point)
                positions.append(p)
            face_positions.append(positions)

        opening_points.append(face_positions)

    return opening_points


def get_3d_structure(g, element="Wall", threshold=0.05):
    print("Getting 3D structure of all {}s...".format(element))
    elements = list()
    coords_m = get_coordinates_map(g)
    for e, _, _ in g.triples((None, RDF.type, FP[element])):
        name = prefixed(g, e).split(":")[-1]

        poly = g.value(e, FP["3d-shape"])
        vertices = get_list_values(g, poly, POLY["points"])
        positions = list()
        for point in vertices:
            p = get_point_position(g, point)
            if element in ["Window", "Entryway"]:
                if p["y"] == 0.0:
                    p["y"] = p["y"] - threshold
                else:
                    p["y"] = p["y"] + threshold

            x, y, z = get_waypoint_coord_wrt_world(g, p, coords_m)
            positions.append((x, y, z))

        faces_nodes = get_list_values(g, poly, POLY["faces"])
        faces = list()
        for f in faces_nodes:
            face_vertices = get_list_from_ptr(g, f)
            face = [vertices.index(point) for point in face_vertices]
            faces.append(face)

        d = {"name": name, "vertices": positions, "faces": faces}
        if element in ["Entryway", "Window"]:
            voids = get_list_values(g, e, FP["voids"])
            d["voids"] = [prefixed(g, v).split(":")[-1] for v in voids]
        elements.append(d)

    return elements


def get_internal_walls(g):
    coords_m = get_coordinates_map(g)
    print("Getting internal walls...")
    wall_planes_by_space = dict()
    for s, r, w in g.triples((None, FP["walls"], None)):
        wall_nodes = get_list_values(g, s, FP["walls"])
        wall_planes = dict()
        for w_ in wall_nodes:
            wall_name = prefixed(g, w_).split(":")[-1]
            poly = g.value(w_, FP["3d-shape"])

            faces_nodes = get_list_values(g, poly, POLY["faces"])
            inner_wall = list()
            for f in faces_nodes:
                face_vertices = get_list_from_ptr(g, f)
                positions = list()
                for point in face_vertices:
                    p = get_point_position(g, point)
                    if p["y"] == 0.0:
                        x, y, z = get_waypoint_coord_wrt_world(g, p, coords_m)
                        positions.append((x, y, z))

                # Only one face (the inner face) will have 4 points aligned with the wall frame
                if len(positions) == 4:
                    positions.append(positions[0])  # Close the polygon
                    inner_wall.append(positions)
            wall_planes[wall_name] = inner_wall

        space_name = prefixed(g, s).split(":")[-1]
        wall_planes_by_space[space_name] = wall_planes

    return wall_planes_by_space


def get_point_positions_in_space(g, space):
    polygon = g.value(space, FP["shape"])

    point_nodes = get_list_values(g, polygon, POLY["points"])

    positions = []
    for point in point_nodes:
        position = get_point_position(g, point)
        positions.append(position)

    return {"name": prefixed(g, space), "points": positions}


def get_coordinates_map(g):
    coordinates_map = {}

    for coord, _, _ in g.triples((None, RDF.type, COORD["PoseCoordinate"])):
        pose = prefixed(g, g.value(coord, COORD["of-pose"]))
        coordinates_map[pose] = get_coordinates(g, coord)

    return coordinates_map


def get_coordinates(g, coord):
    if g.value(coord, COORD["coordinates"]):
        coordinates = dict()
        coord_values = get_list_values(g, coord, COORD["coordinates"])
        for k, v in zip(["x", "y", "z"], coord_values):
            coordinates[k] = v
        cosx = get_list_values(g, coord, COORD["direction-cosine-x"])
        cosx = [v.toPython() for v in cosx if isinstance(v, Literal)]
        coordinates["direction-cosine-x"] = cosx

        cosz = get_list_values(g, coord, COORD["direction-cosine-z"])
        cosz = [v.toPython() for v in cosz if isinstance(v, Literal)]
        coordinates["direction-cosine-z"] = cosz

        coordinates["direction-cosine-y"] = np.cross(
            coordinates["direction-cosine-z"], coordinates["direction-cosine-x"]
        ).tolist()
    else:
        coordinates = {
            "x": get_coord_value(g, coord, "x", default=0.0),
            "y": get_coord_value(g, coord, "y", default=0.0),
            "z": get_coord_value(g, coord, "z", default=0.0),
            "alpha": get_coord_value(g, coord, "alpha", default=0.0),
            "beta": get_coord_value(g, coord, "beta", default=0.0),
        }
    return coordinates


def get_coord_value(g: Graph, coord, key, default=0.0):
    v = g.value(coord, COORD[key], default=default)
    if v is not None and isinstance(v, float):
        return v
    else:
        return v.toPython()


def get_path_positions(g, path):
    positions = list()

    for p in path:
        position = str(prefixed(g, p))
        if "pose" in position:
            positions.append(position)

    return positions


def get_waypoint_coord_wrt_world(g, point, coordinates_map):
    """Gets the coordinates of a point wrt world frame"""

    frame = point["as-seen-by"]
    path = traverse_to_world_origin(g, frame)

    path_positions = get_path_positions(g, path)

    p = np.array([[point["x"]], [point["y"]], [point["z"]], [1]]).astype(float)

    path_positions = path_positions[::-1]
    path_positions.append(0)
    for pose, next_pose in zip(path_positions[:-1], path_positions[1:]):

        coordinates = coordinates_map[pose]
        T = build_transformation_matrix(**coordinates).astype(float)
        if not next_pose == 0:
            if next_pose.count("wall") > 1 and (
                "entryway" not in pose and "window" not in pose
            ):
                T = np.linalg.pinv(T)

        p = np.dot(T, p)

    x = p[0, 0].item()
    y = p[1, 0].item()
    z = p[2, 0].item()

    return x, y, z


def get_waypoint_coord_list(g, points, coordinates_map):
    w_coords = list()
    for p in points:
        x, y, _ = get_waypoint_coord_wrt_world(g, p, coordinates_map)
        w_coords.append([x, y, 0, 1])

    return w_coords
