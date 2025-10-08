import os
import glob
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
    "-o",
    "--output-path",
    type=click.Path(exists=True, resolve_path=True),
    default=os.path.join("."),
    help="Output path for generated variations",
)
def variation(ctx, model_path, variations, output_path, **kwargs):
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
    print(f"Generating {variations} variation(s) from {model_path}")
    print(f"Output path: {output_path}")
    
    generator = generator_for_language_target("fpm-variation", "fpm")
    mm = metamodel_for_language("fpm-variation")
    model = mm.model_from_file(model_path)
    generator(mm, model, output_path, overwrite=True, debug=False, variations=variations)


@floorplan.command(short_help="Complete pipeline: variations -> transform -> generate")
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
    "-o",
    "--output-path",
    type=click.Path(resolve_path=True),
    required=True,
    help="Base output path for all generated files",
)
@click.option(
    "--targets",
    multiple=True,
    type=click.Choice(["occ-grid", "gazebo", "mesh", "tasks", "polyline", "door-keyframes"], case_sensitive=False),
    default=["occ-grid", "gazebo"],
    show_default=True,
    help="Target generators to run (can be specified multiple times)",
)
@click.option(
    "--keep-intermediates",
    is_flag=True,
    help="Keep intermediate variation and JSON-LD files",
)
@click.option(
    "--ros-version",
    type=click.Choice(["ROS2", "ROS1"], case_sensitive=False),
    default="ROS2",
    show_default=True,
    help="ROS version for launch files (used with gazebo target)",
)
@click.option(
    "--ros-pkg",
    type=click.STRING,
    default="floorplan_models",
    show_default=True,
    help="Name of the ROS package (used with gazebo target)",
)
def pipeline(ctx, model_path, variations, output_path, targets, keep_intermediates, ros_version, ros_pkg, **kwargs):
    """Complete pipeline: Generate variations, transform to JSON-LD, and generate artifacts
    
    This command combines the three-step workflow into a single command:
    
    1. Generate FPM variations from a .variation file
    
    2. Transform each variation to JSON-LD
    
    3. Generate final artifacts (occ-grid, gazebo, etc.)
    
    Example:
    
    \b
    floorplan pipeline -m rooms/rooms.variation -n 3 -o output --targets occ-grid --targets gazebo
    
    This is equivalent to running:
    
    \b
    1. floorplan variation -m rooms.variation -n 3 -o output/variations
    2. floorplan transform -m output/variations/rooms_XXXX.fpm -o output/json-ld (for each variation)
    3. floorplan generate -i output/json-ld -o output occ-grid gazebo
    """
    import tempfile
    import shutil
    
    # Create output directory structure
    os.makedirs(output_path, exist_ok=True)
    
    # Use temporary directories or subdirectories based on keep_intermediates flag
    if keep_intermediates:
        variations_path = os.path.join(output_path, "variations")
        jsonld_path = os.path.join(output_path, "json-ld")
        os.makedirs(variations_path, exist_ok=True)
        os.makedirs(jsonld_path, exist_ok=True)
        cleanup_required = False
    else:
        variations_path = tempfile.mkdtemp(prefix="fpm_variations_")
        jsonld_path = tempfile.mkdtemp(prefix="fpm_jsonld_")
        cleanup_required = True
    
    try:
        # Step 1: Generate variations
        click.echo(click.style(f"\n=== Step 1/3: Generating {variations} variation(s) ===", fg="cyan", bold=True))
        click.echo(f"Input: {model_path}")
        click.echo(f"Output: {variations_path}")
        
        ctx.invoke(
            variation,
            model_path=model_path,
            variations=variations,
            output_path=variations_path,
        )
        
        # Find all generated .fpm files
        fpm_files = glob.glob(os.path.join(variations_path, "*.fpm"))

        if not fpm_files:
            raise click.ClickException(f"No .fpm files found in {variations_path}")
        
        click.echo(click.style(f"✓ Generated {len(fpm_files)} variation(s)", fg="green"))
        
        # Step 2: Transform each variation to JSON-LD
        click.echo(click.style(f"\n=== Step 2/3: Transforming variations to JSON-LD ===", fg="cyan", bold=True))

        variation_jsonld_paths = []
        # Transform each variation into its own subdirectory
        for i, fpm_file in enumerate(sorted(fpm_files), 1):
            fpm_basename = os.path.basename(fpm_file)
            # Create subdirectory for this variation (e.g., rooms_1234)
            variation_name = os.path.splitext(fpm_basename)[0]
            variation_jsonld_path = os.path.join(jsonld_path, variation_name)
            os.makedirs(variation_jsonld_path, exist_ok=True)
            
            click.echo(f"[{i}/{len(fpm_files)}] Transforming {fpm_basename}...")
            try:
                ctx.invoke(
                    transform,
                    model_path=fpm_file,
                    output_path=variation_jsonld_path,
                )
                variation_jsonld_paths.append(variation_jsonld_path)

            except Exception as e:
                click.echo(click.style(f"✗ Error transforming {fpm_basename}: {str(e)}", fg="red"))
                if i == 1:
                    # If first variation fails, it's likely a systematic issue
                    raise click.ClickException(f"Transform failed: {str(e)}")
                # Continue with other variations if not the first
                click.echo(f"  Continuing with remaining variations...")
                continue
        
        click.echo(click.style(f"✓ Transformed all variations to JSON-LD", fg="green"))
        
        # Step 3: Generate final artifacts for each JSON-LD variation
        click.echo(click.style(f"\n=== Step 3/3: Generating artifacts ===", fg="cyan", bold=True))
        click.echo(f"Targets: {', '.join(targets)}")
        click.echo(f"Output: {output_path}")

        for i, variation_jsonld_path in enumerate(sorted(variation_jsonld_paths), 1):
            variation_name = os.path.basename(variation_jsonld_path)
            click.echo(click.style(f"\n[{i}/{len(variation_jsonld_paths)}] Generating for {variation_name}", fg="yellow"))

            # Build graph from the JSON-LD directory
            g = build_graph_from_directory([variation_jsonld_path])
            try:
                model_name = get_floorplan_model_name(g)
            except ValueError as e:
                click.echo(click.style(f"✗ Skipping {variation_name}: {str(e)}", fg="red"))
                continue

            # Prepare context object
            obj = {
                "model_name": model_name,
                "g": g
            }

            # Each variation will output to a subfolder named after it.
            variation_output_path = os.path.join(output_path, "artifacts", variation_name)
            os.makedirs(variation_output_path, exist_ok=True)

            params = {
                "inputs": [variation_jsonld_path],
                "base_path": variation_output_path,
                "templates": "."
            }

            # Run each target generator
            for target in targets:
                click.echo(f"  Generating {target}...")

                if target == "occ-grid":
                    get_occ_grid(**obj, **params)
                elif target == "gazebo":
                    gazebo_kwargs = {
                        "ros_version": ros_version,
                        "ros_pkg": ros_pkg,
                        "behavior_config_file": None,
                        "world_frame": "world-frame",
                        "contact_sensors": False,
                        "behaviors": None
                    }
                    door_object_models(**obj, **params, **gazebo_kwargs)
                    gazebo_world(**obj, **params, **gazebo_kwargs)

                    subfolders = ["gazebo/models", "gazebo/worlds/", "3d-mesh", "behaviors"]
                    subpaths = [
                        os.path.join(variation_output_path, subfolder).replace(" ", "\\ ")
                        for subfolder in subfolders
                    ]
                    click.echo(
                        "  For Gazebo to find these models, make sure to add them to the GZ_SIM_RESOURCE_PATH:"
                        "\n  export GZ_SIM_RESOURCE_PATH={}\n".format(":".join(subpaths))
                    )
                elif target == "mesh":
                    get_3d_mesh(**obj, **params)
                elif target == "tasks":
                    get_disinfection_tasks(**obj, **params, dist_to_corner=0.7)
                elif target == "polyline":
                    get_polyline_floorplan(**obj, **params)
                elif target == "door-keyframes":
                    keyframe_kwargs = {
                        "start_frame": 0,
                        "end_frame": 180,
                        "start_state": 0.0,
                        "sampling_interval": 30,
                        "state_change_probability": 0.5
                    }
                    get_keyframes(**obj, **params, **keyframe_kwargs)

        
        click.echo(click.style(f"\n✓ Pipeline completed successfully!", fg="green", bold=True))
        click.echo(f"\nOutput location: {output_path}")
        
        if keep_intermediates:
            click.echo(f"Variations: {variations_path}")
            click.echo(f"JSON-LD: {jsonld_path}")
        
    finally:
        # Cleanup temporary directories if needed
        if cleanup_required:
            if os.path.exists(variations_path):
                shutil.rmtree(variations_path)
            if os.path.exists(jsonld_path):
                shutil.rmtree(jsonld_path)


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
    try:
        model_name = get_floorplan_model_name(g)
    except ValueError as e:
        raise click.ClickException(str(e))

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
