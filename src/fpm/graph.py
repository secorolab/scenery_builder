import random

import os
import glob
import logging
import json
from pyld import jsonld

import numpy as np

import rdflib
from rdflib import RDF, Graph, Literal
from rdflib.tools.rdf2dot import rdf2dot
from transforms3d.quaternions import mat2quat

from fpm import traversal
from fpm.constants import (
    GEO,
    GEOM,
    COORD,
    QUDT,
    QUDT_VOCAB,
    FP,
    POLY,
)
from fpm.utils import build_transformation_matrix

logger = logging.getLogger("floorplan.graph")
logger.setLevel(logging.DEBUG)


def build_graph_from_directory(inputs: tuple, draw_dot=False):
    # Build the graph by reading all composable models in the input folder
    g = rdflib.Graph()
    for input_folder in inputs:
        input_models = glob.glob(os.path.join(input_folder, "*.json"))
        logger.info("Found {} models in {}".format(len(input_models), input_folder))
        for file_path in input_models:
            logger.info("Adding {}".format(file_path))
            g.parse(file_path, format="json-ld")
            logger.debug("\t...done!")

    if draw_dot:
        with open("floorplan.dot", "w+") as dotfile:
            rdf2dot(g, dotfile)

    return g


def save_compact_graph(g: Graph, output_path: str, model_base_iri: str):
    model_name = get_floorplan_model_name(g)
    context = {
        "@context": [
            {
                model_name: f"{model_base_iri}{model_name}/",
            },
            "http://comp-rob2b.github.io/metamodels/qudt.json",
            "https://comp-rob2b.github.io/metamodels/geometry/coordinates.json",
            "https://secorolab.github.io/metamodels/geometry/coordinates.json",
            "https://secorolab.github.io/metamodels/geometry/polytope.json",
            "https://comp-rob2b.github.io/metamodels/geometry/structural-entities.json",
            "https://secorolab.github.io/metamodels/floorplan/floorplan.json",
            "https://comp-rob2b.github.io/metamodels/geometry/spatial-relations.json",
        ]
    }
    d = json.loads(g.serialize(format="json-ld"))
    output_file = os.path.join(output_path, "floorplan.fpm.json")

    compact_graph = jsonld.compact(d, context)

    with open(output_file, "w+") as fp:
        json.dump(compact_graph, fp)

    return output_file


def prefixed(g, node):
    """Return a Notation-3 (N3) prefixed namespace"""
    return node.n3(g.namespace_manager)


def get_list_values(g: Graph, subject, predicate):
    ptr = g.value(subject, predicate)
    if ptr == RDF.nil:
        return []
    values = get_list_from_ptr(g, ptr)
    return values


def get_list_from_ptr(g: Graph, ptr):
    result_list = []
    while True:
        result_list.append(g.value(ptr, RDF.first))
        ptr = g.value(ptr, RDF.rest)
        if ptr == RDF.nil:
            break

    return result_list


def get_point_position(g: Graph, point):
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

    # Convert units if not in M
    unit_multiplier = get_unit_multiplier(g, coordinates)

    return {
        "name": name,
        "x": float(x) * unit_multiplier,
        "y": float(y) * unit_multiplier,
        "z": float(z) * unit_multiplier,
        "as-seen-by": prefixed(g, asb),
    }


def get_floorplan_model_name(g: Graph):
    floorplan = g.value(predicate=RDF.type, object=FP["FloorPlan"])
    if floorplan is None:
        raise ValueError("No FloorPlan found.")
    model_name = prefixed(g, floorplan).split(":")[1]

    return model_name


def traverse_to_world_origin(g: Graph, frame):
    # Go through the geometric relation predicates
    pred_filter = traversal.filter_by_predicates([GEOM["with-respect-to"], GEOM["of"]])
    # Algorithm to traverse the graph
    open_set = traversal.BreadthFirst

    # Set beginning and end point
    pref, f = frame.split(":")
    root = g.namespace_manager.expand_curie(frame)
    goal = g.namespace_manager.expand_curie("{}:world-frame".format(pref))

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


def get_transformation_matrix_wrt_frame(g: Graph, root, target):
    # TODO Refactor this since it's duplicated with utils.py
    # Only used for the object instances (doors)

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


def get_space_points(g: Graph):
    floorplan = g.value(predicate=RDF.type, object=FP["FloorPlan"])

    # Get the list of spaces
    logger.info("Querying all spaces...")
    spaces = get_list_values(g, floorplan, FP["spaces"])
    logger.info("Found %d spaces", len(spaces))

    # for each space, find the polygon
    logger.info("Get all points of a space...")
    space_points = []
    for space in spaces:
        space_points_json = get_point_positions_in_space(g, space)
        space_points.append(space_points_json)

    return space_points


def get_unit_multiplier(g: Graph, element_id):
    # Convert units if not in M
    pose_units = list(g.objects(element_id, QUDT["unit"]))
    for unit in pose_units:
        if unit in [QUDT_VOCAB["MilliM"], QUDT_VOCAB["M"]]:
            break
    if unit == QUDT_VOCAB["M"]:
        m = 1
    elif unit == QUDT_VOCAB["MilliM"]:
        m = 0.001
    else:
        raise ValueError("Unknown unit", unit)
    return m


def get_element_points(g: Graph, element_type="Wall"):
    logger.info("Querying all {}s...".format(element_type))
    element_points = list()
    for element, _, _ in g.triples((None, RDF.type, FP[element_type])):
        unit_multiplier = get_unit_multiplier(g, element)
        element_points_json = get_point_positions_in_space(g, element)

        height = g.value(element, FP["height"]).toPython() * unit_multiplier
        element_points_json["height"] = height

        element_points.append(element_points_json)

    return element_points


def get_opening_points(g: Graph, element="Entryway"):
    logger.info("Querying all {}s...".format(element))
    opening_points = list()
    for opening, _, _ in g.triples((None, RDF.type, FP[element])):
        poly = g.value(opening, FP["3d-shape"])
        assert poly is not None
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


def get_3d_structure(g: Graph, element="Wall", threshold=0.05):
    """
    Return the 3D structure of non-cylindrical elements
    """
    logger.info("Getting 3D structure of all {}s...".format(element))
    elements = list()
    coords_m = get_coordinates_map(g)
    for e, _, _ in g.triples((None, RDF.type, FP[element])):
        name = prefixed(g, e).split(":")[-1]

        poly = g.value(e, FP["3d-shape"])
        if g.value(poly, RDF.type) != POLY["Polyhedron"]:
            continue
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


def get_internal_walls(g: Graph):
    coords_m = get_coordinates_map(g)
    logger.info("Getting internal walls...")
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


def get_point_positions_in_space(g: Graph, space):
    logger.debug("Querying points from polygon attribute for %s", prefixed(g, space))
    polygon = g.value(space, FP["shape"])

    point_nodes = get_list_values(g, polygon, POLY["points"])

    positions = []
    logger.debug("Querying point positions")
    for point in point_nodes:
        position = get_point_position(g, point)
        positions.append(position)

    return {"name": prefixed(g, space), "points": positions}


def get_coordinates_map(g: Graph):
    coordinates_map = {}

    for coord, _, _ in g.triples((None, RDF.type, COORD["PoseCoordinate"])):
        pose = prefixed(g, g.value(coord, COORD["of-pose"]))
        coordinates_map[pose] = get_coordinates(g, coord)

    return coordinates_map


def get_coordinates(g: Graph, coord):
    """
    coord: @id of the PoseCoordinate element
    """
    unit_multiplier = get_unit_multiplier(g, coord)

    if g.value(coord, COORD["coordinates"]):
        coordinates = dict()
        coord_values = get_list_values(g, coord, COORD["coordinates"])
        for k, v in zip(["x", "y", "z"], coord_values):
            coordinates[k] = v.toPython() * unit_multiplier
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
        logger.debug("Coordinates specified as individual values")
        coordinates = {
            "x": get_coord_value(g, coord, "x", default=0.0) * unit_multiplier,
            "y": get_coord_value(g, coord, "y", default=0.0) * unit_multiplier,
            "z": get_coord_value(g, coord, "z", default=0.0) * unit_multiplier,
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


def get_path_positions(g: Graph, path):
    positions = list()

    for p in path:
        position = str(prefixed(g, p))
        if "pose" in position:
            positions.append(position)

    return positions


def get_waypoint_coord_wrt_world(g: Graph, point, coordinates_map):
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


def get_waypoint_coord_list(g: Graph, points, coordinates_map):
    w_coords = list()
    for p in points:
        x, y, _ = get_waypoint_coord_wrt_world(g, p, coordinates_map)
        w_coords.append([x, y, 0, 1])

    return w_coords


def _coord_to_np_matrix(coord, scale=1.0):
    t = np.zeros((4, 4))
    t[0, 3] = coord.get("x")
    t[1, 3] = coord.get("y")
    t[2, 3] = coord.get("z")
    t[3, 3] = scale
    t[:3, 0] = coord.get("direction-cosine-x")
    t[:3, 1] = coord.get("direction-cosine-y")
    t[:3, 2] = coord.get("direction-cosine-z")

    return t


def get_pose_transform_wrt_world(g: Graph, pose_ref):
    coord = get_coordinates(g, pose_ref)
    m = _coord_to_np_matrix(coord)
    pose = g.value(pose_ref, COORD["of-pose"])
    frame = g.value(pose, GEOM["with-respect-to"])
    transformation_path = traverse_to_world_origin(g, prefixed(g, frame))

    for t in transformation_path[::-1]:
        if g.value(t, RDF["type"]) == GEO["Frame"]:
            continue
        new_pose_ref = g.value(predicate=COORD["of-pose"], object=t)
        new_m = get_coordinates(g, new_pose_ref)
        new_m = _coord_to_np_matrix(new_m)
        m = np.dot(new_m, m)

    return m


def get_frame_transform(g: Graph, filter_str: str):
    matrices = list()
    for s, p, o in g.triples((None, RDF["type"], COORD["PoseReference"])):
        if filter_str not in str(s):
            continue
        m = get_pose_transform_wrt_world(g, s)
        matrices.append(m)

    return matrices


def get_frame_tree(g: Graph, poses=None):
    frames = dict()
    if poses is None:
        pose_list = g.subjects(RDF["type"], COORD["PoseReference"])
    else:
        pose_list = poses

    for pose_ref in pose_list:
        coord = get_coordinates(g, pose_ref)
        pose = g.value(pose_ref, COORD["of-pose"])
        frame = g.value(pose, GEOM["with-respect-to"])
        transformation_path = traverse_to_world_origin(g, prefixed(g, frame))
        frame = g.value(pose, GEOM["of"])
        for t in transformation_path[::-1]:
            if g.value(t, RDF["type"]) == GEO["Frame"]:
                m = _coord_to_np_matrix(coord)
                d = {
                    "parent_frame_id": prefixed(g, t).split(":")[-1],
                    "frame_id": prefixed(g, frame).split(":")[-1],
                    "p": list(m[:3, 3]),
                    "q": list(mat2quat(m[:3, :3])),
                }
                # TODO This is not optimal, rewrite to avoid loops for transforms we already know
                frames[frame] = d
                frame = t
            else:
                new_pose_ref = g.value(predicate=COORD["of-pose"], object=t)
                coord = get_coordinates(g, new_pose_ref)
    return frames


def get_floorplan_elements(g: Graph, floorplan_elements: list):
    poses = list()
    for element in floorplan_elements:
        for s, p, o in g.triples((None, RDF["type"], FP[element])):
            shape3d = g.value(s, FP["3d-shape"])
            shape_type = g.value(shape3d, RDF["type"])
            if shape_type == POLY["Polyhedron"]:
                point = g.value(shape3d, POLY["points"] / RDF["first"])
            elif shape_type == POLY["Cylinder"]:
                point = g.value(shape3d, POLY["base"] / POLY["center"])

            position_ref = g.value(
                predicate=COORD["of-position"] / GEOM["of"], object=point
            )
            asb = g.value(position_ref, COORD["as-seen-by"])
            assert g.value(asb, RDF["type"]) == GEO["Frame"]
            pose_ref = g.value(predicate=COORD["of-pose"] / GEOM["of"], object=asb)
            poses.append(pose_ref)
    return poses


def get_spaces(g: Graph):
    boundary_query = """
    SELECT DISTINCT ?boundary ?space ?shape
    WHERE {
        ?boundary rdf:type fpm:SpaceBoundary .
        ?boundary fpm:spaces/rdf:rest*/rdf:first ?space .
        ?space rdf:type fpm:Space  .
        ?boundary fpm:shape ?shape .
    }
    """
    space_nodes = g.subjects(predicate=RDF["type"], object=FP["Space"])
    spaces = []

    for node in space_nodes:
        result = g.query(
            boundary_query, initNs={"fpm": FP, "rdf": RDF}, initBindings={"space": node}
        )
        planes = []
        for r, s, shape in result:
            point = g.value(shape, POLY["points"] / RDF["first"])
            position_ref = g.value(
                predicate=COORD["of-position"] / GEOM["of"], object=point
            )
            asb = g.value(position_ref, COORD["as-seen-by"])
            assert g.value(asb, RDF["type"]) == GEO["Frame"]
            pose_ref = g.value(predicate=COORD["of-pose"] / GEOM["of"], object=asb)
            normal = get_list_values(g, pose_ref, COORD["direction-cosine-z"])
            normal = [x.toPython() for x in normal]
            pose_wrt_world = get_pose_transform_wrt_world(g, pose_ref)
            planes.append(
                {
                    "name": prefixed(g, r).split(":")[-1],
                    "position": pose_wrt_world[:3, 3].round(4),
                    "normal": normal,
                    "color": random.choices(range(256), k=3),
                }
            )
        spaces.append({"space": prefixed(g, node).split(":")[-1], "planes": planes})
    return spaces
