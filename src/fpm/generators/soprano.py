import logging
import numpy as np
import rdflib
from rdflib import Graph, RDF
from transforms3d.quaternions import mat2quat

from fpm.constants import FP, POLY, GEO, COORD, GEOM, BDD_ENV
from fpm.graph import (
    get_3d_structure,
    get_coordinates_map,
    prefixed,
    get_unit_multiplier,
    get_list_values,
    get_point_position,
    get_waypoint_coord_wrt_world,
    get_list_from_ptr,
    get_pose_transform_wrt_world,
    get_coordinates,
    _coord_to_np_matrix,
    get_frame_tree,
    get_floorplan_elements,
)
from fpm.utils import render_model_template, get_output_path, save_file
from ifcld.interpreters.namespaces import IFC_CONCEPTS

logger = logging.getLogger("floorplan.generators.soprano")
logger.setLevel(logging.DEBUG)


def get_dim_and_center(element):
    points = np.array(element.get("vertices"))
    min_values = np.min(points, axis=0)
    max_values = np.max(points, axis=0)
    dims = np.abs(max_values - min_values)
    center = min_values + dims / 2
    return {"id": element.get("name"), "center": center, "dimensions": dims}


def gen_tts_wall_description(g, base_path, **kwargs):
    logger.info("Generating wall description for simulator...")
    template_path = kwargs.get("template_path")
    output_path = get_output_path(base_path, "soprano")

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
        model.append(w)

    render_model_template(
        model,
        output_path,
        "HDT-wall-description.json",
        "soprano/walls.json.jinja",
        template_path,
    )


def get_outlet_milling_task(g: Graph, element_type="Opening", **kwargs):
    logger.info("Getting 3D structure of all {}s...".format(element_type))
    elements = list()
    coords_m = get_coordinates_map(g)
    for e, _, _ in g.triples((None, RDF.type, FP[element_type])):
        name = prefixed(g, e).split(":")[-1]
        space, workspace = get_space_and_workspace(g, e)
        wall = (g.value(e, FP["voids"] / RDF["first"]),)
        assert len(wall) == 1
        wall = wall[0]
        wall_id = prefixed(g, wall).split(":")[-1]

        poly = g.value(e, FP["3d-shape"])
        if g.value(poly, RDF.type) != POLY["Cylinder"]:
            continue

        logger.debug("%s: %s", name, prefixed(g, g.value(poly, RDF.type)))

        base = g.value(poly, POLY["base"])
        unit_multiplier = get_unit_multiplier(g, poly)
        height = g.value(poly, POLY["height"]).toPython() * unit_multiplier
        axis = get_list_values(g, poly, POLY["axis"])

        # TODO unit conversion for non-zero values for the center
        center = g.value(base, POLY["center"])
        radius = g.value(base, POLY["radius"]).toPython() * unit_multiplier
        logger.debug("radius: %s, depth: %s", radius, height)

        # Find center of base circle, use axis and height to project 2nd face and get its center
        p = get_point_position(g, center)
        pp = dict(**p)
        pp["z"] = axis[-1].toPython() * height
        positions = list()
        for coord in [p, pp]:
            x, y, z = get_waypoint_coord_wrt_world(g, coord, coords_m)
            positions.append((x, y, z))
        logger.debug("Milling vector: %s", positions)

        plane = get_milling_plane(g, e)
        start = g.value(plane, GEO["start"])
        start_pose_ref = get_start_pose_coords(g, start)
        m_start_wrt_world = get_pose_transform_wrt_world(g, start_pose_ref)
        nav_pose = translate_nav_pose(g, start_pose_ref, **kwargs)

        logger.debug("Position: [%s, %s, %s]", round(x, 2), round(y, 2), round(z, 2))
        element = {
            "name": name,
            "thickness": height,
            "milling_vector": positions,
            "nav_pose": nav_pose,
            "radius": radius,
            "origin": m_start_wrt_world[:3, 3],
            "voids": wall_id,
            "unit": "M",  # Internally the scenery builder always uses Meters
            "action": "milling",
            "space": space,
            "workspace": workspace,
        }
        elements.append(element)

    return elements


def translate_nav_pose(g: Graph, pose_ref, x=0.0, y=0.0, z=0.0, **_):
    # Navigation actions require a robot transformation wrt to the outlet/duct
    # Rotation: X axis of the robot must be parallel to the wall.
    # This (currently) matches the space boundary frame in the IFC model
    translation = np.array(
        [
            [1.0, 0.0, 0.0, x],
            [0.0, 0.0, 1.0, y],
            [0.0, 1.0, 0.0, z],
            [0.0, 0.0, 0.0, 1.0],
        ]
    )
    t_wrt_world = get_pose_transform_wrt_world(g, pose_ref)
    nav_pose = np.dot(t_wrt_world, translation)
    return nav_pose


def get_milling_plane(g: Graph, opening):
    plane = get_list_values(g, opening, GEO["vectors"])
    assert len(plane) == 1
    plane = plane[0]

    return plane


def get_space_and_workspace(g: Graph, element):
    workspace = g.value(element, BDD_ENV["has-workspace"])
    space = g.value(
        predicate=BDD_ENV["has-workspace"] / BDD_ENV["has-workspace"],
        object=workspace,
    )
    return prefixed(g, space).split(":")[-1], prefixed(g, workspace).split(":")[-1]


def get_start_pose_coords(g: Graph, point):
    frame = g.value(predicate=GEO["origin"], object=point)
    start_pose = g.value(predicate=GEOM["of"], object=frame)
    start_pose_ref = g.value(predicate=COORD["of-pose"], object=start_pose)
    return start_pose_ref


def get_duct_milling_task(g: Graph, element_type="Opening", **kwargs):
    logger.info("Getting 3D structure of all {}s...".format(element_type))
    elements = []
    for e, _, _ in g.triples((None, RDF.type, FP[element_type])):
        name = prefixed(g, e).split(":")[-1]

        space, workspace = get_space_and_workspace(g, e)

        wall = (g.value(e, FP["voids"] / RDF["first"]),)
        assert len(wall) == 1
        wall = wall[0]
        wall_id = prefixed(g, wall).split(":")[-1]

        poly = g.value(e, FP["3d-shape"])
        if g.value(poly, RDF.type) == POLY["Cylinder"]:
            continue

        logger.debug("%s: %s", name, prefixed(g, g.value(poly, RDF.type)))

        plane = get_milling_plane(g, e)
        start = g.value(plane, GEO["start"])
        end = g.value(plane, GEO["end"])
        start_pose_ref = get_start_pose_coords(g, start)

        m_start_wrt_world = get_pose_transform_wrt_world(g, start_pose_ref)

        end_position = get_point_position(g, end)
        coords_m = get_coordinates_map(g)
        end_position_coord = get_waypoint_coord_wrt_world(g, end_position, coords_m)
        end_position_coord = np.array(end_position_coord)

        # Find both faces that are parallel to ground
        faces = rdflib.collection.Collection(
            g,
            g[poly : POLY["faces"]].__next__(),
        )
        all_faces = []
        for f in faces:
            face = rdflib.collection.Collection(g, f)
            face_coords = []
            for point in face:
                p = get_point_position(g, point)

                x, y, z = get_waypoint_coord_wrt_world(g, p, coords_m)
                face_coords.append((x, y, z))
            face_coords = np.array(face_coords)
            if np.allclose(face_coords[:, 2], face_coords[0, 2]):
                all_faces.append(face_coords)

        # Milling action: Vector of milling is their direction (e.g., bottom-top)
        assert len(all_faces) == 2
        milling_vector = []
        for f in all_faces:
            center_xy = np.mean(f, axis=0)
            milling_vector.append(center_xy)

        # Sort bottom to top
        milling_vector.sort(key=lambda x: x[2], reverse=True)
        length = abs(milling_vector[0][2] - milling_vector[1][2])
        logger.info("Length: %s", length)

        # Calculate width
        base = all_faces[0]
        v_thickness = m_start_wrt_world[:3, 3] - end_position_coord
        v1 = abs(base[0, :] - base[1, :])
        v2 = abs(base[0, :] - base[-1, :])
        if np.dot(v1, v_thickness) == 0.0:
            width = v1.sum()
            thickness = v2.sum()
        else:
            width = v2.sum()
            thickness = v1.sum()
        logger.info("Width: %s, Thickness: %s", width, thickness)

        nav_pose = translate_nav_pose(g, start_pose_ref, **kwargs)

        element = {
            "name": name,
            "width": width,
            "thickness": thickness,
            "length": length,
            "milling_vector": milling_vector,
            "origin": m_start_wrt_world[:3, 3],
            "nav_pose": nav_pose,
            "voids": wall_id,
            "unit": "M",  # Internally the scenery builder always uses Meters
            "action": "milling",
            "space": space,
            "workspace": workspace,
        }
        elements.append(element)

    return elements


def convert_to_nav2_goal_format(goals: list) -> list:
    nav2_goals = []
    for g in goals:
        m = g["nav_pose"]
        milling_dir = np.array(g["milling_vector"])
        milling_dir = milling_dir[1] - milling_dir[0]
        milling_dir = milling_dir / np.linalg.norm(milling_dir)
        t = {
            "name": g["name"],
            "voids": g["voids"],
            "nav2_goal": {
                "p": list(m[:3, 3]),
                "q": list(mat2quat(m[:3, :3])),
            },
            "milling_vector": list(milling_dir),
            "thickness": g["thickness"],
            "position": list(g["origin"]),
            "unit": g["unit"],
            "action": g["action"],
            "space": g["space"],
        }
        if g.get("radius"):
            t["radius"] = g["radius"]
            t["type"] = "outlet"
        else:
            t["width"] = g["width"]
            t["length"] = g["length"]
            t["type"] = "duct"
        nav2_goals.append(t)
    return nav2_goals


def query_milling_tasks(g: Graph, **kwargs) -> list:
    tasks = []

    logger.info("Generating task description for outlets")
    outlets = get_outlet_milling_task(g, "Opening", **kwargs)
    tasks.extend(outlets)

    logger.info("Generating task description for ducts")
    ducts = get_duct_milling_task(g, "Opening", **kwargs)
    tasks.extend(ducts)

    return tasks


def gen_tts_task_description(g, base_path, **kwargs):
    logger.info("Generating task description...")
    template_path = kwargs.get("template_path")
    output_path = get_output_path(base_path, "soprano")

    tasks = query_milling_tasks(g, **kwargs)

    save_file(
        output_path,
        "HDT-task-description.json",
        [
            {
                "entity_name": "KukaPlatform1",
                "tasks": convert_to_nav2_goal_format(tasks),
            },
            {
                "entity_name": "Human1",
                "tasks": [],
            },
        ],
    )

    return tasks


def gen_ros_frames(g, base_path, **kwargs):
    logger.info("Generating ROS frames launch file...")
    template_path = kwargs.get("template_path")
    output_path = get_output_path(base_path, "ros")
    floorplan_elements = ["Space", "Opening", "Wall", "Door", "Entryway"]
    element_poses = get_floorplan_elements(g, floorplan_elements)
    frames = get_frame_tree(g, element_poses)
    render_model_template(
        frames,
        output_path,
        "frames-ros2.launch",
        "ros/frames-ros2.launch.jinja",
        template_path,
    )


def get_avt_tasks(g, base_path, **kwargs):
    logger.info("Generating tasks for the AVT component...")
    template_path = kwargs.get("template_path")
    output_path = get_output_path(base_path, "soprano")
    tasks = query_milling_tasks(g, **kwargs)
    render_model_template(
        convert_to_nav2_goal_format(tasks),
        output_path,
        "AVT-tasks.json",
        "soprano/avt-tasks.json.jinja",
        template_path,
    )


def get_soprano_tasks(g, base_path, **kwargs):
    template_path = kwargs.get("template_path")
    output_path = get_output_path(base_path, "soprano")
    tasks = query_milling_tasks(g, **kwargs)
    render_model_template(
        convert_to_nav2_goal_format(tasks),
        output_path,
        "nav-goals.yaml",
        "soprano/nav-goals.yaml.jinja",
        template_path,
    )
