import numpy as np
from rdflib import Graph, RDF

from fpm.constants import FP, POLY
from fpm.graph import (
    get_3d_structure,
    get_coordinates_map,
    prefixed,
    get_unit_multiplier,
    get_list_values,
    get_point_position,
    get_waypoint_coord_wrt_world,
    get_list_from_ptr,
)
from fpm.utils import render_model_template, get_output_path


def get_dim_and_center(element):
    points = np.array(element.get("vertices"))
    min_values = np.min(points, axis=0)
    max_values = np.max(points, axis=0)
    dims = np.abs(max_values - min_values)
    center = min_values + dims / 2
    return {"id": element.get("name"), "center": center, "dimensions": dims}


def gen_tts_wall_description(g, base_path, **kwargs):
    print("Wall description")
    template_path = kwargs.get("template_path")
    output_path = get_output_path(base_path, "tts")

    entryways_elements = get_3d_structure(g, "Entryway")
    window_elements = get_3d_structure(g, "Window")
    openings = dict()
    for entryway in entryways_elements:
        voids = entryway.get("voids")
        e = get_dim_and_center(entryway)
        for w in voids:
            openings.setdefault(w, list()).append(e)

    for window in window_elements:
        voids = window.get("voids")
        e = get_dim_and_center(window)
        openings.setdefault(voids, list()).append(e)

    wall_elements = get_3d_structure(g, "Wall")
    model = list()
    for wall in wall_elements:
        w = get_dim_and_center(wall)
        w["cutouts"] = openings.get(wall.get("name"))
        print(w)
        model.append(w)

    render_model_template(
        model,
        output_path,
        "walls.json",
        "tts/walls.json.jinja",
        template_path,
    )


def get_outlet_milling_task(g: Graph, element="Opening", threshold=0.05):
    print("Getting 3D structure of all {}s...".format(element))
    elements = list()
    coords_m = get_coordinates_map(g)
    for e, _, _ in g.triples((None, RDF.type, FP[element])):
        name = prefixed(g, e).split(":")[-1]

        poly = g.value(e, FP["3d-shape"])
        if g.value(poly, RDF.type) != POLY["Cylinder"]:
            continue

        # print(name, g.value(poly, RDF.type))

        base = g.value(poly, POLY["base"])
        unit_multiplier = get_unit_multiplier(g, poly)
        height = g.value(poly, POLY["height"]).toPython() * unit_multiplier
        axis = get_list_values(g, poly, POLY["axis"])

        # TODO unit conversion for non-zero values for the center
        center = g.value(base, POLY["center"])
        radius = g.value(base, POLY["radius"]).toPython() * unit_multiplier

        # TODO Milling action: find center of base circle, use axis and height to project 2nd face and get its center
        p = get_point_position(g, center)
        pp = dict(**p)
        pp["z"] = axis[-1].toPython() * height
        positions = list()
        for coord in [p, pp]:
            x, y, z = get_waypoint_coord_wrt_world(g, coord, coords_m)
            # print(round(x, 2), "\t", round(y, 2), "\t", round(z, 2))
            positions.append((x, y, z))

        # TODO Navigation actions: Add a robot transform from:
        # 1) base circle of outlets
        # 2) center of either face for ducts
        # z=0
        # Translation: (1.0, 1.0) in M
        # Rotation: X axis must be parallel to the wall
        # TODO Are there any conventions I can use for the axes of their object placements?
        nav_pose = dict(**p)
        nav_pose["z"] = axis[-1].toPython() * -1.0
        nav_pose["y"] = nav_pose["y"] + 1.0
        x, y, z = get_waypoint_coord_wrt_world(g, nav_pose, coords_m)
        # print(round(x, 2), "\t", round(y, 2), "\t", round(z, 2))

        element = {
            "name": name,
            "depth": height,
            "milling_vector": positions,
            "nav_pose": [x, y, z],
            "radius": radius,
        }
        elements.append(element)

    return elements


def get_duct_milling_task(g: Graph, element="Opening"):
    # TODO Both actions: find both faces that are parallel to ground and get their centers.
    # TODO Milling action: Vector of milling is their direction (e.g., top-bottom)
    print("Getting 3D structure of all {}s...".format(element))
    elements = list()
    coords_m = get_coordinates_map(g)
    for e, _, _ in g.triples((None, RDF.type, FP[element])):
        name = prefixed(g, e).split(":")[-1]

        poly = g.value(e, FP["3d-shape"])
        if g.value(poly, RDF.type) == POLY["Cylinder"]:
            continue

        vertices = get_list_values(g, poly, POLY["points"])
        positions = list()
        for point in vertices:
            p = get_point_position(g, point)

            x, y, z = get_waypoint_coord_wrt_world(g, p, coords_m)
            positions.append((x, y, z))

        faces_nodes = get_list_values(g, poly, POLY["faces"])
        faces = list()
        for f in faces_nodes:
            face_vertices = get_list_from_ptr(g, f)
            face = [vertices.index(point) for point in face_vertices]
            faces.append(face)

    # ducts = get_3d_structure(g, "Opening")
    # for duct in ducts:
    #     print(duct)
    return elements


def gen_tts_task_description(g, base_path, **kwargs):
    print("Task description")
    template_path = kwargs.get("template_path")
    output_path = get_output_path(base_path, "tts")

    outlets = get_outlet_milling_task(g, "Opening")
    for outlet in outlets:
        print(outlet)

    # ducts = get_duct_milling_task(g, "Opening")

    return outlets
