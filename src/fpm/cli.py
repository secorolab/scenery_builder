import os
import click

from fpm.graph import build_graph_from_directory, get_floorplan_model_name
from fpm.generators.gazebo import gazebo_world, door_object_models
from fpm.generators.tasks import get_tasks
from fpm.generators.occ_grid import get_occ_grid
from fpm.generators.mesh import get_3d_mesh
from fpm.generators.polyline import get_polyline_floorplan
from fpm.generators.door_keyframes import get_keyframes


@click.group()
def floorplan():
    pass


@floorplan.group()
@click.pass_context
@click.option(
    "--inputs",
    "--input-path",
    "-i",
    type=click.Path(exists=True, resolve_path=True),
    required=True,
    multiple=True,
    help="Path with JSON-LD models to be used as inputs",
)
@click.option(
    "--output-path",
    "-o",
    "--outputs",
    type=click.Path(exists=True, resolve_path=True),
    default=os.path.join("."),
    help="Output path for generated artefacts",
)
@click.option(
    "--templates",
    type=click.Path(exists=True, resolve_path=True),
    default=os.path.join("."),
    help="Path with Jinja templates",
)
def generate(ctx, inputs, output_path, **kwargs):
    print(kwargs)

    g = build_graph_from_directory(inputs)
    model_name = get_floorplan_model_name(g)

    ctx.ensure_object(dict)
    ctx.obj[model_name] = model_name
    ctx.obj["graph"] = g

    print("End of generate command")


@generate.command()
@click.pass_context
def mesh(ctx, **kwargs):
    print("test")
    print(ctx.obj)
    print(kwargs)
    g = ctx.obj["graph"]
    # get_3d_mesh(g, output_path, **kwargs)


@generate.command()
@click.pass_context
@click.option(
    "--waypoint-dist-to-corner",
    type=click.FLOAT,
    default=0.7,
    show_default=True,
    help="Distance between generated waypoints and a space's corner",
)
def tasks(ctx, **kwargs):
    g = ctx.obj["graph"]
    # get_tasks(g, output_path, **kwargs)


@generate.command()
@click.pass_context
@click.option(
    "--ros-version",
    type=click.STRING,
    default="ros2",
    show_default=True,
    help="ROS version for launch files",
)
@click.option(
    "--ros-pkg",
    type=click.STRING,
    default="floorplan_models",
    show_default=True,
    help="Name of the ROS package where gazebo models",
)
def gazebo(ctx, **kwargs):
    g = ctx.obj["graph"]
    # door_object_models(g, output_path, **kwargs)
    # gazebo_world(g, model_name, output_path, **kwargs)


@generate.command()
@click.pass_context
@click.option(
    "--map-laser-height",
    type=click.FLOAT,
    default=0.7,
    show_default=True,
    help="Map: Height of the laser to generate the occupancy grid",
)
@click.option(
    "--map-border",
    type=click.INT,
    default=50,
    show_default=True,
    help="Map: Border the occupancy grid",
)
@click.option(
    "--map-resolution",
    type=click.FLOAT,
    default=0.05,
    show_default=True,
    help="Map: Resolution of the pgm file in m/pixel",
)
@click.option(
    "--map-occupied-threshold",
    type=click.FLOAT,
    default=0.65,
    show_default=True,
    help="Map: Probability of a pixel at which a cell is considered occupied",
)
@click.option(
    "--map-free-threshold",
    type=click.FLOAT,
    default=0.196,
    show_default=True,
    help="Map: Probability of a pixel at which a cell is considered free",
)
@click.option(
    "--map-negate",
    type=click.FLOAT,
    default=0.0,
    show_default=True,
    help="Map: Whether the occupied/free/unknown semantics of the occupancy grid should be reversed",
)
@click.option(
    "--map-unknown-value",
    type=click.INT,
    default=200,
    show_default=True,
    help="Map: Value for cells to be considered unknown in the occupancy grid",
)
@click.option(
    "--map-occupied-value",
    type=click.INT,
    default=0,
    show_default=True,
    help="Map: Value for cells to be considered occupied in the occupancy map",
)
@click.option(
    "--map-free-value",
    type=click.INT,
    default=255,
    show_default=True,
    help="Map: Value for cells to be considered free in the occupancy map",
)
def occ_grid(ctx, **kwargs):
    g = ctx.obj["graph"]
    # get_occ_grid(g, output_path, **kwargs)


@generate.command()
@click.pass_context
def polyline(ctx, **kwargs):
    g = ctx.obj["graph"]
    # get_polyline_floorplan(g, output_path, **kwargs)


@generate.command()
@click.pass_context
@click.option(
    "--keyframe-start",
    type=click.INT,
    default=0,
    show_default=True,
    help="Timestamp of the first keyframe",
)
@click.option(
    "--keyframe-end",
    type=click.INT,
    default=180,
    show_default=True,
    help="Timestamp of the last keyframe",
)
@click.option(
    "--keyframe-start-state",
    type=click.FLOAT,
    default=0.0,
    show_default=True,
    help="Start joint angle of the doors",
)
@click.option(
    "--keyframe-sampling-interval",
    type=click.INT,
    default=30,
    show_default=True,
    help="Sampling interval",
)
@click.option(
    "--keyframe-state-change-probability",
    type=click.FLOAT,
    default=0.5,
    show_default=True,
    help="Probability of a door changing states at the next interval",
)
def door_keyframes(ctx, **kwargs):
    g = ctx.obj["graph"]
    # get_keyframes(output_path, **kwargs)


if __name__ == "__main__":
    import sys

    if sys.argv[0] == "blender":
        args = sys.argv[sys.argv.index("--") + 1 :]
    else:
        args = sys.argv[1:]

    floorplan.main(args=args)
