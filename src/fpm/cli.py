import os
import click

from fpm.graph import build_graph_from_directory, get_floorplan_model_name
from fpm.generators.gazebo import gazebo_world, door_object_models
from fpm.generators.tasks import get_disinfection_tasks
from fpm.generators.occ_grid import get_occ_grid
from fpm.generators.mesh import get_3d_mesh
from fpm.generators.polyline import get_polyline_floorplan
from fpm.generators.door_keyframes import get_keyframes
from textx import generator_for_language_target, metamodel_for_language


def configure(ctx, param, filename):
    if not filename:
        return
    import tomllib

    ctx.default_map = dict()
    with open(filename, "rb") as f:
        data = tomllib.load(f)

    cmd_defaults = data.get("generate", {})
    ctx.default_map.update(cmd_defaults)


def _gen_docs(ctx, param, gen):
    if not gen:
        return
    from fpm.utils import load_template

    def _save_file(cmd_name, cmd_info):
        content = template.render(cmd=cmd_info, lstrip_blocks=True, trim_blocks=True)
        with open("docs/cli/{}.md".format(cmd_name), "w+") as f:
            f.write(content)

    template = load_template(template_name="cli/command.md.jinja")

    info = ctx.to_info_dict()
    # TODO This is a workaround to include the usage from click
    # See https://github.com/pallets/click/issues/2992
    info["command"]["usage"] = ctx.get_usage()
    info["command"]["parent"] = "CLI"
    fp_cmd = info.get("command")
    for cmd_n1 in ctx.command.list_commands(ctx):
        cmd2 = ctx.command.get_command(ctx, cmd_n1)
        sub_ctx = ctx._make_sub_context(cmd2)
        usage = cmd2.get_usage(sub_ctx).replace("Usage: ", "")
        info["command"]["commands"][cmd_n1]["usage"] = usage
        if isinstance(cmd2, click.Group):
            # Groups
            for cmd_n2 in cmd2.list_commands(ctx):
                cmd3 = cmd2.get_command(ctx, cmd_n2)
                sub_ctx3 = sub_ctx._make_sub_context(cmd3)
                usage = cmd3.get_usage(sub_ctx3).replace("Usage: ", "")
                info["command"]["commands"][cmd_n1]["commands"][cmd_n2]["usage"] = usage

    _save_file("floorplan", info.get("command"))
    commands = fp_cmd.get("commands")
    for cmd_n1, cmd_info in commands.items():
        cmd_info["parent"] = info.get("info_name")
        _save_file(cmd_n1, cmd_info)
        for cmd_n2, cmd_info2 in cmd_info.get("commands", dict()).items():
            cmd_info2["parent"] = cmd_n1
            _save_file(cmd_n2, cmd_info2)


def config_behaviors(ctx, param, filename):
    if not filename:
        return
    import yaml

    with open(filename, "rb") as f:
        config = yaml.safe_load(f)

    ctx.obj["behaviors"] = config


@click.group()
@click.option(
    "--docs",
    is_flag=True,
    is_eager=True,
    callback=_gen_docs,
    help="Generate the documentation for this CLI",
)
def floorplan(docs):
    """CLI for the scenery builder artefact generation"""
    pass


@floorplan.command(short_help="Transform an FPM model into JSON-LD")
@click.pass_context
@click.option(
    "-m",
    "--model",
    "model_path",
    type=click.Path(exists=True, resolve_path=True, file_okay=True, dir_okay=False),
    required=True,
    help="Path to the fpm model to transform into JSON-LD",
)
@click.option(
    "-o",
    "--output-path",
    type=click.Path(exists=True, resolve_path=True),
    default=os.path.join("."),
    help="Output path for generated artefacts",
)
def transform(ctx, model_path, output_path, **kwargs):
    """Transform an FPM model into JSON-LD

    This command is equivalent to using TextX's CLI to transform the fpm model:

    ```
    textx generate --target json-ld --overwrite <model.fpm> -o <output path>
    ```

    This requires that the [FloorPlan DSL](https://github.com/secorolab/FloorPlan-DSL) is installed.
    """
    print(model_path, output_path)
    generator = generator_for_language_target("fpm", "json-ld")
    mm = metamodel_for_language("fpm")
    model = mm.model_from_file(model_path)
    generator(mm, model, output_path, overwrite=True)


@floorplan.group(
    chain=True,
    short_help="Generate execution artefacts from JSON-LD models",
)
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
    """Generate execution artefacts from JSON-LD models"""

    print(kwargs)

    g = build_graph_from_directory(inputs)
    model_name = get_floorplan_model_name(g)

    ctx.ensure_object(dict)
    ctx.obj["model_name"] = model_name
    ctx.obj["g"] = g


@generate.command(short_help="Generate a 3D-mesh of the floorplan")
@click.pass_context
def mesh(ctx, **kwargs):
    """Generate a 3D-mesh in STL or gltF 2.0 format"""
    get_3d_mesh(**ctx.obj, **ctx.parent.params, **kwargs)


@generate.command(short_help="Generate navigation waypoints for all rooms")
@click.pass_context
@click.option(
    "--dist-to-corner",
    type=click.FLOAT,
    default=0.7,
    show_default=True,
    help="Distance between generated waypoints and a space's corner",
)
def tasks(ctx, **kwargs):
    """Generate navigation waypoints for each room in the floorplan

    The current version creates a YAML file for each room with the waypoints for a disinfection task (one waypoint per corner).
    The files currently have the following structure:

    ```yaml
    id: <space name>
    task:
      - name: <space name>
        type: waypoint_following
        waypoints:
        - {id: <space name>-point-0000, x: <float>, y: <float>, yaw: <float>, z: <float>}
        - {id: <space name>-point-0001, x: <float>, y: <float>, yaw: <float>, z: <float>}
        - {id: <space name>-point-0002, x: <float>, y: <float>, yaw: <float>, z: <float>}
        - {id: <space name>-point-0003, x: <float>, y: <float>, yaw: <float>, z: <float>}
    ```
    """
    get_disinfection_tasks(**ctx.obj, **ctx.parent.params, **kwargs)


@generate.command(short_help="Generate artefacts for the Gazebo simulation")
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
@click.option(
    "--behaviors",
    "behavior_config_file",
    type=click.Path(dir_okay=False, exists=True, resolve_path=True),
    help="Path to YAML file with door behavior parameters",
    show_default=True,
    callback=config_behaviors,
)
@click.option(
    "--world-frame",
    default="world-frame",
    show_default=True,
    help="ID of the world frame in the input models",
)
@click.option(
    "--contact-sensors",
    is_flag=True,
    help="Flag to add contact sensors to walls and door",
)
def gazebo(ctx, **kwargs):
    """Generate Gazebo world, models and launch files"""
    door_object_models(**ctx.obj, **ctx.parent.params, **kwargs)
    gazebo_world(**ctx.obj, **ctx.parent.params, **kwargs)

    base_path = ctx.parent.params.get("base_path")
    subfolders = ["gazebo/models", "gazebo/worlds/", "3d-mesh", "behaviors"]
    subpaths = [
        os.path.join(base_path, subfolder).replace(" ", "\ ")
        for subfolder in subfolders
    ]
    click.echo(
        "For Gazebo to find these models, make sure to add them to the GZ_SIM_RESOURCE_PATH:"
        "\nexport GZ_SIM_RESOURCE_PATH={}\n".format(":".join(subpaths))
    )


@generate.command(short_help="Generate the occupancy grid map of the floorplan")
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


@generate.command(short_help="Generate a 3D polyline representation of the floorplan")
@click.pass_context
def polyline(ctx, **kwargs):
    """Generate a 3D polyline representation of the floorplan"""
    get_polyline_floorplan(**ctx.obj, **ctx.parent.params, **kwargs)


@generate.command(
    short_help="Generate the timed-behaviour spec for the floorplan doors"
)
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
