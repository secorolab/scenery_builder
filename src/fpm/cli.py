import os
import click

from fpm.graph import build_graph_from_directory, get_floorplan_model_name
from fpm.generators.gazebo import gazebo_world, door_object_models
from fpm.generators.tasks import get_tasks
from fpm.generators.occ_grid import get_occ_grid
from fpm.generators.mesh import get_3d_mesh
from fpm.generators.polyline import get_polyline_floorplan
from fpm.generators.door_keyframes import get_keyframes


def configure(ctx, param, filename):
    if not filename:
        return
    import tomllib

    ctx.default_map = dict()
    with open(filename, "rb") as f:
        data = tomllib.load(f)

    cmd_defaults = data.get("generate", {})
    ctx.default_map.update(cmd_defaults)


@click.group()
def floorplan():
    pass


@floorplan.group(chain=True)
@click.pass_context
@click.option(
    "-i",
    "--inputs",
    "--input-path",
    type=click.Path(exists=True, resolve_path=True),
    required=True,
    multiple=True,
    help="Path with JSON-LD models to be used as inputs",
)
@click.option(
    "-o",
    "--outputs",
    "--output-path",
    "base_path",
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
@click.option(
    "-c",
    "--config",
    type=click.Path(dir_okay=False),
    is_eager=True,
    expose_value=False,
    help="Read values from TOML config file",
    show_default=True,
    callback=configure,
)
def generate(ctx, inputs, **kwargs):

    print(kwargs)

    g = build_graph_from_directory(inputs)
    model_name = get_floorplan_model_name(g)

    ctx.ensure_object(dict)
    ctx.obj["model_name"] = model_name
    ctx.obj["g"] = g


@generate.command()
@click.pass_context
def mesh(ctx, **kwargs):
    """Generate a 3D-mesh in STL or gltF 2.0 format"""
    get_3d_mesh(**ctx.obj, **ctx.parent.params, **kwargs)


@generate.command()
@click.pass_context
@click.option(
    "--dist-to-corner",
    type=click.FLOAT,
    default=0.7,
    show_default=True,
    help="Distance between generated waypoints and a space's corner",
)
def tasks(ctx, **kwargs):
    """Generate disinfection tasks for each room in the floorplan"""
    get_tasks(**ctx.obj, **ctx.parent.params, **kwargs)


@generate.command()
@click.pass_context
@click.option(
    "--ros-version",
    type=click.Choice(["ROS2", "ROS1"], case_sensitive=False),
    default="ROS2",
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
    """Generate Gazebo world, models and launch files"""
    door_object_models(**ctx.obj, **ctx.parent.params, **kwargs)
    gazebo_world(**ctx.obj, **ctx.parent.params, **kwargs)


@generate.command()
@click.pass_context
@click.option(
    "--laser-height",
    type=click.FLOAT,
    default=0.7,
    show_default=True,
    help="Height of the laser to generate the occupancy grid",
)
@click.option(
    "--border",
    type=click.INT,
    default=50,
    show_default=True,
    help="Border the occupancy grid image file",
)
@click.option(
    "--resolution",
    type=click.FLOAT,
    default=0.05,
    show_default=True,
    help="Resolution of the pgm file in m/pixel",
)
@click.option(
    "--occupied-threshold",
    type=click.FLOAT,
    default=0.65,
    show_default=True,
    help="Probability of a pixel at which a cell is considered occupied",
)
@click.option(
    "--free-threshold",
    type=click.FLOAT,
    default=0.196,
    show_default=True,
    help="Probability of a pixel at which a cell is considered free",
)
@click.option(
    "--negate",
    type=click.INT,
    default=0,
    show_default=True,
    help="Whether the occupied/free/unknown semantics of the occupancy grid should be reversed",
)
@click.option(
    "--unknown-value",
    type=click.INT,
    default=200,
    show_default=True,
    help="Value for cells to be considered unknown in the occupancy grid",
)
@click.option(
    "--occupied-value",
    type=click.INT,
    default=0,
    show_default=True,
    help="Value for cells to be considered occupied in the occupancy map",
)
@click.option(
    "--free-value",
    type=click.INT,
    default=255,
    show_default=True,
    help="Value for cells to be considered free in the occupancy map",
)
def occ_grid(ctx, **kwargs):
    """Generate the occupancy grid map of the floorplan"""
    get_occ_grid(**ctx.obj, **ctx.parent.params, **kwargs)


@generate.command()
@click.pass_context
def polyline(ctx, **kwargs):
    """Generate a 3D polyline representation of the floorplan"""
    get_polyline_floorplan(**ctx.obj, **ctx.parent.params, **kwargs)


@generate.command()
@click.pass_context
@click.option(
    "--start-frame",
    type=click.INT,
    default=0,
    show_default=True,
    help="Timestamp of the first keyframe",
)
@click.option(
    "--end-frame",
    type=click.INT,
    default=180,
    show_default=True,
    help="Timestamp of the last keyframe",
)
@click.option(
    "--start-state",
    type=click.FLOAT,
    default=0.0,
    show_default=True,
    help="Start joint angle of the doors",
)
@click.option(
    "--sampling-interval",
    type=click.INT,
    default=30,
    show_default=True,
    help="Sampling interval",
)
@click.option(
    "--state-change-probability",
    "--state-change-prob",
    type=click.FLOAT,
    default=0.5,
    show_default=True,
    help="Probability of a door changing states at the next interval",
)
def door_keyframes(ctx, **kwargs):
    """Generate the sampled keyframes for doors with time-based behaviours"""
    get_keyframes(**ctx.obj, **ctx.parent.params, **kwargs)


if __name__ == "__main__":
    import sys

    if sys.argv[0] == "blender":
        args = sys.argv[sys.argv.index("--") + 1 :]
    else:
        args = sys.argv[1:]

    floorplan.main(args=args)
