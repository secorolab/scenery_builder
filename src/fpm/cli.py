import os
import click
import logging
import tempfile

from fpm import __version__
from fpm.generators.dot import visualize_frame_tree
from fpm.generators.prov import (
    fpm_prov_generation_graph,
    artefact_prov_generation_graph,
    var_prov_generation_graph,
    var_prov_metadata,
    artefact_prov_metadata,
    jsonld_prov_metadata,
)
from fpm.graph import (
    build_graph_from_directory,
    get_floorplan_model_name,
    save_compact_graph,
)
from fpm.generators.gazebo import gazebo_world, door_object_models
from fpm.generators.tasks import get_disinfection_tasks
from fpm.generators.occ_grid import get_occ_grid
from fpm.generators.mesh import get_3d_mesh
from fpm.generators.polyline import get_polyline_floorplan
from fpm.generators.door_keyframes import get_keyframes
from fpm.generators.soprano import (
    gen_tts_wall_description,
    gen_tts_task_description,
    gen_ros_frames,
)
from fpm.generators.scenery import generate_fpm_rep_from_rdf
from textx import generator_for_language_target, metamodel_for_language

from fpm.logging import logger as floorplan_logger

floorplan_logger.setLevel(logging.DEBUG)

logger = logging.getLogger("floorplan.cli")
logger.setLevel(logging.DEBUG)


def configure(ctx, param, filename):
    if not filename:
        return
    import tomllib

    logger.debug("Using config file: %s", filename)

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
@click.version_option(__version__)
@click.pass_context
def floorplan(ctx, docs):
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
    type=click.Path(resolve_path=True),
    default=os.path.join("."),
    help="Output path for generated artefacts",
)
@click.option(
    "--prov",
    is_flag=True,
    help="Flag to whether to generate a PROV graph of this activity",
)
@click.option(
    "--model-base-iri",
    type=click.STRING,
    default="https://secorolab.github.io/models/floorplan/",
    show_default=True,
    help="Default model IRI to be used as a prefix in the PROV models",
)
@click.option(
    "--debug",
    is_flag=True,
)
def transform(ctx, model_path, output_path, debug, **kwargs):
    """Transform an FPM model into JSON-LD

    This command is equivalent to using TextX's CLI to transform the fpm model:

    ```
    textx generate --target json-ld --overwrite <model.fpm> -o <output path>
    ```

    This requires that the [FloorPlan DSL](https://github.com/secorolab/FloorPlan-DSL) is installed.
    """
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    logger.debug("transform command arguments: %s", kwargs)
    logger.debug("%s %s", model_path, output_path)
    generator = generator_for_language_target("fpm", "json-ld")
    mm = metamodel_for_language("fpm")
    model = mm.model_from_file(model_path)
    try:
        if debug:
            res = generator(mm, model, output_path=output_path, overwrite=True)
        else:
            with tempfile.TemporaryDirectory(prefix="scg_") as tmpdir:
                tmp_path = os.path.join(tmpdir, "json-ld")
                generator(mm, model, output_path=tmp_path, overwrite=True)
                g = build_graph_from_directory([tmp_path])
            output_file = save_compact_graph(
                g, output_path, model_base_iri=kwargs.get("model_base_iri")
            )
            res = [output_file]
    except Exception as e:
        logger.error(f"Error transforming model: {e}")

    jsonld_prov_metadata(model_path, res)
    if kwargs.get("prov"):
        fpm_prov_generation_graph(model, model_path, res, output_path, **kwargs)


@floorplan.command(short_help="Generate FPM variations from a variation model")
@click.pass_context
@click.option(
    "-m",
    "--model",
    "model_path",
    type=click.Path(exists=True, resolve_path=True, file_okay=True, dir_okay=False),
    required=True,
    help="Path to the .variation model file",
)
@click.option(
    "-n",
    "--variations",
    "--num-variations",
    type=click.INT,
    default=1,
    show_default=True,
    help="Number of variations to generate",
)
@click.option(
    "-s",
    "--seed",
    type=click.INT,
    default=None,
    show_default=True,
    help="Random seed for reproducible variation generation",
)
@click.option(
    "-o",
    "--output-path",
    type=click.Path(exists=True, resolve_path=True),
    default=os.path.join("."),
    help="Output path for generated variations",
)
@click.option(
    "--prov",
    is_flag=True,
    help="Flag to whether to generate a PROV graph of this activity",
)
@click.option(
    "--model-base-iri",
    type=click.STRING,
    default="https://secorolab.github.io/models/",
    show_default=True,
    help="Default model IRI to be used as a prefix in the PROV models",
)
def variation(ctx, model_path, variations, seed, output_path, **kwargs):
    """Generate FPM model variations from a variation specification

    This command generates multiple FPM model variations by applying probability
    distributions to spatial attributes as specified in a .variation file.

    Each resulting model follows the format <floorplan_name>_<seed>.fpm and can be
    further transformed into JSON-LD and other artefacts.

    This command is equivalent to using TextX's CLI:

    ```
    textx generate <variation model> --target fpm --variations <number> -o <output path>
    ```

    This requires that the [FloorPlan DSL](https://github.com/secorolab/FloorPlan-DSL) is installed.

    See https://github.com/secorolab/FloorPlan-DSL/blob/devel/docs/tutorials/variation.md
    for more information on creating variation models.
    """
    logger.info(f"Generating {variations} variation(s) from {model_path}")
    logger.info(f"Output path: {output_path}")
    if seed is not None:
        logger.info(f"Using seed: {seed}")

    generator = generator_for_language_target("fpm-variation", "fpm")
    mm = metamodel_for_language("fpm-variation")
    model = mm.model_from_file(model_path)
    try:
        f, res = generator(
            mm,
            model,
            output_path,
            overwrite=True,
            debug=False,
            variations=variations,
            seed=seed,
        )
    except Exception as e:
        logger.error(f"Error generating variations: {e}")

    var_prov_metadata(model_path, f, res)

    if kwargs.get("prov"):
        var_prov_generation_graph(model_path, f, res, output_path, **kwargs)


@floorplan.command(
    short_help="Generate FPM JSON-LD models from an IFCLD model",
)
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
@click.option(
    "--debug",
    is_flag=True,
)
def ifc(ctx, model_path, output_path, debug, **kwargs):

    generate_fpm_rep_from_rdf(model_path, output_path, debug)


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
@click.option(
    "--prov",
    is_flag=True,
    help="Flag to whether to generate a PROV graph of this activity",
)
@click.option(
    "--model-base-iri",
    type=click.STRING,
    default="https://secorolab.github.io/models/",
    show_default=True,
    help="Default model IRI to be used as a prefix in the PROV models",
)
def generate(ctx, inputs, **kwargs):
    """Generate execution artefacts from JSON-LD models"""

    logger.debug("generate command arguments: inputs: %s, kwargs: %s", inputs, kwargs)
    _load_graph_to_ctx(ctx, inputs)


def _load_graph_to_ctx(ctx, input_paths):
    logger.debug("Loading graph from paths: %s", input_paths)
    g = build_graph_from_directory(input_paths)
    try:
        model_name = get_floorplan_model_name(g)
    except ValueError as e:
        raise click.ClickException(str(e))

    ctx.ensure_object(dict)
    ctx.obj["model_name"] = model_name
    ctx.obj["g"] = g


@generate.command(short_help="Generate a 3D-mesh of the floorplan")
@click.pass_context
@click.option(
    "--include-doors",
    is_flag=True,
    help="Flag to indicate that the mesh should include the door meshes",
)
@click.option(
    "--format",
    type=click.Choice(["stl", "gltf"], case_sensitive=False),
    default=["stl"],
    show_default=True,
    multiple=True,
    help="Output format of the 3D mesh",
)
def mesh(ctx, **kwargs):
    """Generate a 3D-mesh in STL or gltF 2.0 format"""
    output_file = get_3d_mesh(**ctx.obj, **ctx.parent.params, **kwargs)

    artefact_prov_metadata(ctx.parent.params.get("inputs"), output_file)
    prov = ctx.parent.params.get("prov")
    if prov:
        artefact_prov_generation_graph(
            ctx.obj.get("model_name"),
            ctx.parent.params.get("inputs"),
            output_file,
            "3D-Mesh",
            ctx.parent.params.get("base_path"),
            model_base_iri=ctx.parent.params.get("model_base_iri"),
        )


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
    output_files = []
    files = door_object_models(**ctx.obj, **ctx.parent.params, **kwargs)
    output_files.extend(files)

    files = gazebo_world(**ctx.obj, **ctx.parent.params, **kwargs)
    output_files.extend(files)

    artefact_prov_metadata(ctx.parent.params.get("inputs"), output_files)
    prov = ctx.parent.params.get("prov")
    if prov:
        artefact_prov_generation_graph(
            ctx.obj.get("model_name"),
            ctx.parent.params.get("inputs"),
            output_files,
            "GazeboModel",
            ctx.parent.params.get("base_path"),
            model_base_iri=ctx.parent.params.get("model_base_iri"),
        )

    base_path = ctx.parent.params.get("base_path")
    subfolders = ["gazebo/models", "gazebo/worlds/", "3d-mesh", "behaviors"]
    subpaths = [
        os.path.join(base_path, subfolder).replace(" ", "\\ ")
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
@click.option(
    "--source",
    type=click.Choice(["fpm", "bim"], case_sensitive=False),
    default="fpm",
    show_default=True,
    help="Type of source model being used",
)
@click.option(
    "--visualize-frames",
    type=click.Choice(
        ["wall", "door", "entryway", "space", "opening"], case_sensitive=False
    ),
    help="Which element frames to visualize",
    multiple=True,
)
def occ_grid(ctx, **kwargs):
    """Generate the occupancy grid map of the floorplan"""
    logger.info("Generating occupancy grid...")
    logger.debug("Arguments: %s", kwargs)
    output_files = get_occ_grid(**ctx.obj, **ctx.parent.params, **kwargs)

    artefact_prov_metadata(
        ctx.parent.params.get("inputs"), output_files, ignored_extensions=[".jpg"]
    )
    prov = ctx.parent.params.get("prov")
    if prov:
        artefact_prov_generation_graph(
            ctx.obj.get("model_name"),
            ctx.parent.params.get("inputs"),
            output_files,
            "OccupancyGrid",
            ctx.parent.params.get("base_path"),
            model_base_iri=ctx.parent.params.get("model_base_iri"),
        )


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


@generate.command(short_help="Generate a 3D polyline representation for SOPRANO")
@click.pass_context
def soprano_poly(ctx, **kwargs):
    """Generate a 3D polyline representation of the floorplan"""
    get_polyline_floorplan(**ctx.obj, **ctx.parent.params, **kwargs)


@generate.command(help="Generate artefacts for the SOPRANO GUI")
@click.pass_context
def soprano_gui():
    pass


@generate.command()
@click.pass_context
@click.option(
    "--robot-translation-x",
    "x",
    type=click.FLOAT,
    default=-1.0,
    show_default=True,
    help="Translation of the robot in x wrt to a task element for a navigation goal",
)
@click.option(
    "--robot-translation-z",
    "z",
    type=click.FLOAT,
    default=1.7,
    show_default=True,
    help="Translation of the robot in z wrt to a task element for a navigation goal",
)
@click.option(
    "--ros-frames",
    is_flag=True,
    help="Generate a ROS launch file with frame transformations for task elements",
)
@click.option(
    "--visualize",
    is_flag=True,
    help="Generate images visualizing the environment and tasks",
)
def soprano_hdt(ctx, **kwargs):
    """Generate the artefacts for the SOPRANO TTS simulator"""
    logger.info("Generating artefacts for the SOPRANO TTS simulator...")
    logger.debug("Arguments: %s", kwargs)
    gen_tts_wall_description(**ctx.obj, **ctx.parent.params, **kwargs)
    outlets, ducts = gen_tts_task_description(**ctx.obj, **ctx.parent.params, **kwargs)
    if kwargs.get("ros_frames"):
        gen_ros_frames(**ctx.obj, **ctx.parent.params, **kwargs)
    if kwargs.get("visualize"):
        logger.info("Visualizing milling task for the outlets on occupancy grid")
        get_occ_grid(
            **ctx.obj, **ctx.parent.params, **kwargs, outlets=outlets, source="bim"
        )
        get_occ_grid(
            **ctx.obj, **ctx.parent.params, **kwargs, ducts=ducts, source="bim"
        )
        logger.info("Visualizing frames on occupancy grid")
        get_occ_grid(
            **ctx.obj,
            **ctx.parent.params,
            **kwargs,
            visualize_frames=["outlet", "duct", "wall"],
            source="bim",
        )


@floorplan.command(short_help="Visualize aspects of a floorplan model")
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
    "--output-path",
    type=click.Path(exists=True, resolve_path=True),
    default=os.path.join("."),
    help="Output path for generated artefacts",
)
def visualize(ctx, inputs, output_path, **kwargs):
    floorplan_elements = ["Space", "Opening", "Wall", "Door", "Entryway", "DoorPanel"]
    print(ctx.obj, ctx.parent.params)
    _load_graph_to_ctx(ctx, inputs)
    visualize_frame_tree(
        output_path=output_path,
        floorplan_elements=floorplan_elements,
        **ctx.obj,
        # **ctx.parent.params,
        **kwargs,
    )


if __name__ == "__main__":
    import sys

    if sys.argv[0] == "blender":
        args = sys.argv[sys.argv.index("--") + 1 :]
    else:
        args = sys.argv[1:]

    floorplan.main(args=args)
