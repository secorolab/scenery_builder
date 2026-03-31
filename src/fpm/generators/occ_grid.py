import os
import logging

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageOps
from matplotlib.image import AxesImage

from fpm.graph import (
    get_space_points,
    get_coordinates_map,
    get_floorplan_model_name,
    get_element_points,
    get_opening_points,
    get_waypoint_coord_wrt_world,
    get_waypoint_coord_list,
    get_frame_transform,
)
from fpm.utils import load_template, save_file, get_output_path
from fpm.visualization.plot import plot_2d_frame, plot_2d_robot

logger = logging.getLogger("floorplan.generators.occ_grid")
logger.setLevel(logging.DEBUG)


def generate_occ_grid(g, map_name, **custom_args):
    plt.clf()
    logger.info("Map name: {}".format(map_name))

    resolution = custom_args.get("resolution", 0.05)

    unknown = custom_args.get("unknown_value", 200)
    occupied = custom_args.get("occupied_value", 0)
    free = custom_args.get("free_value", 255)
    border = custom_args.get("border", 50)

    points = []
    directions = []

    logger.debug("Getting coordinates map")
    coords_m = get_coordinates_map(g)
    logger.debug("Getting space points")
    space_points = get_space_points(g)
    for s in space_points:
        logger.debug("Getting waypoint coords")
        w_coords = get_waypoint_coord_list(g, s.get("points"), coords_m)

        w_coords = np.array(w_coords)
        points.append(w_coords)

        # Get the left/right, top/bottom of each space
        directions.append(
            [
                np.amax(w_coords[:, 1]),  # north
                np.amin(w_coords[:, 1]),  # south
                np.amax(w_coords[:, 0]),  # east
                np.amin(w_coords[:, 0]),  # west
            ]
        )

    # Get the left/right, top/bottom of the entire map
    directions = np.array(directions)
    north = np.amax(directions[:, 0])
    south = np.amin(directions[:, 1])
    east = np.amax(directions[:, 2])
    west = np.amin(directions[:, 3])

    # Get center of the map
    center = [
        -float(abs(west) + border * resolution / 2),
        -float(abs(south) + border * resolution / 2),
        0,
    ]

    metadata = get_map_metadata(map_name, center, **custom_args)

    # Create canvas
    floor = (
        int(abs(east - west) / resolution) + border,
        int(abs(north - south) / resolution) + border,
    )

    im = Image.new("L", floor, unknown)
    draw = ImageDraw.Draw(im)

    # Draw free space from floorplan spaces (rooms)
    logger.debug("Drawing free space")
    draw_floorplan_element(points, draw, free, west=west, south=south, **custom_args)

    # Draw obstacles (walls and columns)
    logger.debug("Drawing walls")
    draw_floorplan_obstacle(
        g, "Wall", draw, west, south, occupied, coords_m, **custom_args
    )
    logger.debug("Drawing columns")
    draw_floorplan_obstacle(
        g, "Column", draw, west, south, occupied, coords_m, **custom_args
    )
    logger.debug("Drawing dividers")
    draw_floorplan_obstacle(
        g, "Divider", draw, west, south, occupied, coords_m, **custom_args
    )

    # Clear out wall openings; mark them as free space
    logger.debug("Drawing entryways")
    draw_floorplan_opening(
        g, "Entryway", draw, west, south, free, coords_m, **custom_args
    )
    # draw_floorplan_opening(g, "Window", draw, west, south, resolution, border, free, coords_m)

    return metadata, im


def draw_floorplan_obstacle(g, element, draw, west, south, fill, coords_map, **kwargs):
    column_points = get_element_points(g, element)
    c_points = list()

    laser_height = kwargs.get("laser_height", 0.7)
    for s in column_points:
        height = s.get("height")
        if laser_height > height:
            # Don't process elements that are below the laser height
            # This assumes that walls, columns, and dividers start at z=0 (from the floor)
            continue

        c_coords = get_waypoint_coord_list(g, s.get("points"), coords_map)

        c_coords = np.array(c_coords)
        c_points.append(c_coords)

    draw_floorplan_element(
        c_points,
        draw,
        fill,
        west=west,
        south=south,
        **kwargs,
    )


def draw_floorplan_opening(g, element, draw, west, south, fill, coords_map, **kwargs):
    opening_points = get_opening_points(g, element)
    resolution = kwargs.get("resolution", 0.05)
    laser_height = kwargs.get("laser_height", 0.7)

    source = kwargs.get("source", "fpm")

    all_points = list()
    for opening in opening_points:
        opening_height_max = 0.0
        opening_height_min = float("inf")
        for face in opening:
            points = [get_waypoint_coord_wrt_world(g, p, coords_map) for p in face]
            if source == "fpm":
                z_vals = [p.get("z") for p in face]
            else:
                z_vals = [z for x, y, z in points]
            if not np.all(np.array(z_vals) == z_vals[0]):
                # Only process faces that are parallel to the floor (where the z is the same)
                continue

            # TODO how to make the 3d object slightly larger than the wall when we can't rely on a convention for the axis direction
            # TODO Check if there is an alternative for floorplan models that do follow a convention
            if source == "fpm":
                f_coords, opening_height_max, opening_height_min = (
                    get_fpm_opening_points(
                        face,
                        opening_height_max,
                        opening_height_min,
                        resolution,
                        g,
                        coords_map,
                    )
                )
            else:
                f_coords, opening_height_max, opening_height_min = (
                    get_bim_opening_points(
                        points, opening_height_max, opening_height_min
                    )
                )
            if opening_height_min <= laser_height <= opening_height_max:
                f_coords = np.array(f_coords)
                all_points.append(f_coords)

    draw_floorplan_element(all_points, draw, fill, west=west, south=south, **kwargs)


def get_bim_opening_points(points, opening_height_max, opening_height_min):
    # BIM: No assumptions for frames
    coords = list()
    for x, y, z in points:
        coords.append([x, y, 0, 1])
        if z > opening_height_max:
            opening_height_max = z
        elif z < opening_height_min:
            opening_height_min = z

    return coords, opening_height_max, opening_height_min


def get_fpm_opening_points(
    face, opening_height_max, opening_height_min, resolution, graph, coords_map
):
    # FPM: Assumptions for direction of XYZ vectors
    coords = list()
    for p in face:
        if p["y"] == 0.0:
            p["y"] = p["y"] - resolution
        else:
            p["y"] = p["y"] + resolution
        x, y, z = get_waypoint_coord_wrt_world(graph, p, coords_map)
        coords.append([x, y, 0, 1])
        if z > opening_height_max:
            opening_height_max = z
        elif z < opening_height_min:
            opening_height_min = z

    return coords, opening_height_max, opening_height_min


def draw_floorplan_element(points, draw, fill, **kwargs):
    west = kwargs.get("west")
    south = kwargs.get("south")
    resolution = kwargs.get("resolution", 0.05)
    border = kwargs.get("border", 50)

    for shape in points:
        element_shape = get_2d_shape(west, south, resolution, border, shape=shape)
        draw_2d_shape(draw, element_shape, fill=fill, **kwargs)


def draw_2d_shape(draw, shape, fill, outline=None, width=1, **kwargs):
    draw.polygon(
        shape[:, 0:2].flatten().tolist(), fill=fill, outline=outline, width=width
    )


def get_2d_shape(west, south, resolution, border, points=None, shape=None):
    if shape is None:
        shape = points[0 : int(len(points) / 2), 0:2]
    shape[:, 0] = (shape[:, 0] + abs(west)) / resolution
    shape[:, 1] = (shape[:, 1] + abs(south)) / resolution
    shape += border / 2
    shape = shape.astype(int)

    return shape


def get_map_metadata(map_name, center: list, **custom_args):
    map_metadata = {
        "resolution": custom_args.get("resolution", 0.05),
        "origin": center,
        "occupied_thresh": custom_args.get("occupied_threshold", 0.65),
        "free_thresh": custom_args.get("free_threshold", 0.196),
        "negate": custom_args.get("negate", 0),
        "image": "{}.pgm".format(map_name),
        "laser_height": custom_args.get("laser_height", 0.7),
    }

    return map_metadata


def get_occ_grid(g, base_path, save=True, **kwargs):
    output_files = []
    map_name = get_floorplan_model_name(g)
    output_path = get_output_path(base_path, "maps")
    if "{{model_name}}" in output_path:
        output_path = output_path.replace("{{model_name}}", map_name)
        if not os.path.exists(output_path):
            os.makedirs(output_path)

    map_metadata, im = generate_occ_grid(g, map_name, **kwargs)
    center = map_metadata.get("origin", [])

    if save:
        # Save the occupancy grid and its metadata
        file_name = f"{map_name}.yaml"
        f = save_file(output_path, file_name, map_metadata)
        output_files.append(f)

        img = ImageOps.flip(im)
        name_image = f"{map_name}.pgm"
        f = save_file(output_path, name_image, img)
        output_files.append(f)

    if kwargs.get("draw_map"):
        fig, _ = draw_map(im, center, **kwargs)
        name_image = f"{map_name}.jpg"
        plt.tight_layout()
        fig.savefig(os.path.join(output_path, name_image), dpi=300, bbox_inches="tight")

    if kwargs.get("outlets"):
        logger.debug("Drawing outlet task elements")
        draw_tasks(
            im,
            center,
            tasks="outlets",
            map_name=map_name,
            output_path=output_path,
            **kwargs,
        )
    if kwargs.get("ducts"):
        logger.debug("Drawing duct task elements")
        draw_tasks(
            im,
            center,
            tasks="ducts",
            map_name=map_name,
            output_path=output_path,
            **kwargs,
        )

    for frame_type in kwargs.get("visualize_frames", []):
        plt.clf()
        logger.debug("Drawing frames for %s", frame_type)
        draw_frames(
            g,
            im,
            center,
            map_name=map_name,
            output_path=output_path,
            frame_type=frame_type,
            **kwargs,
        )

    return output_files


def _get_im_map(im, center: list[float], **kwargs) -> AxesImage:
    resolution = kwargs.get("resolution", 0.05)
    w, h = im.size
    orig_x, orig_y, _ = center
    imax = plt.imshow(
        im,
        cmap="gray",
        interpolation="none",
        origin="upper",
        extent=(
            orig_x,
            (w * resolution) - abs(orig_x),
            (h * resolution) - abs(orig_y),
            orig_y,
        ),
    )

    return imax


def draw_map(im, center: list[float], grid=False, grid_resolution=1.0, **kwargs):
    imax = _get_im_map(im, center, **kwargs)
    fig = imax.get_figure()
    ax = fig.get_axes().pop()
    ax.yaxis.set_inverted(False)
    ax.set_aspect("equal", adjustable="box")

    if grid:
        x_val = ax.get_xticks()
        ax.set_xticks(np.arange(x_val[0], x_val[-1], step=grid_resolution), minor=True)
        y_val = ax.get_yticks()
        ax.set_yticks(np.arange(y_val[0], y_val[-1], step=grid_resolution), minor=True)

        ax.grid(grid, alpha=0.5, which="both")

    ax.set_xlim(center[0])
    ax.set_ylim(center[1])

    return fig, ax


def draw_tasks(im, center, tasks, **kwargs):
    logger.info("Drawing tasks: %s", tasks)
    fig, ax = draw_map(im, center, grid=True, **kwargs)
    for task in kwargs.get(tasks, []):
        name = task["name"]
        nav_pose = task.get("nav_pose")
        plot_2d_robot(ax, nav_pose, 1.4, 1.9)
        nav_pose[3, 3] = 0.25
        plot_2d_frame(ax, nav_pose, name)

        milling_task = np.array(task.get("milling_vector"))

        ax.scatter(
            milling_task[0, 0],
            milling_task[0, 1],
            c="red",
            marker=".",
            s=15,
        )
        ax.plot(milling_task[:, 0], milling_task[:, 1], color="yellow")
    map_name = kwargs.get("map_name")
    output_path = kwargs.get("output_path")
    name_image = "tasks-{}-{}.{}".format(tasks, map_name, "jpg")

    fig.savefig(os.path.join(output_path, name_image), dpi=300)


def draw_frames(g, im, center, map_name, output_path, frame_type, **kwargs):
    fig, ax = draw_map(im, center, grid=True, **kwargs)
    name_image = "{}-frames-{}.{}".format(frame_type, map_name, "jpg")
    matrices = get_frame_transform(g, frame_type)
    for m in matrices:
        m[3, 3] = 0.25
        plot_2d_frame(ax, m)

    fig.savefig(os.path.join(output_path, name_image), dpi=300)
