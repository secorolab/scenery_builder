import os
import click

from fpm.utils import load_config_file
from fpm.graph import build_graph_from_directory, get_floorplan_model_name
from fpm.generators.ros import generate_launch_file
from fpm.generators.gazebo import generate_sdf_file
from fpm.generators.tasks import generate_task_specification
from fpm.transformations.tasks import get_all_disinfection_tasks
from fpm.transformations.objects import get_all_object_models, get_all_object_instances


@click.group()
def floorplan():
    pass


def door_object_models(config, g):
    template_path = config["templates"]["path"]

    object_models = get_all_object_models(g)

    for model in object_models:
        model_name = model["name"][5:]
        output_path = get_output_path(config, "gazebo_models", model_name)
        generate_sdf_file(
            model,
            output_path,
            "model.sdf",
            "gazebo/door.sdf.jinja",
            template_path=template_path,
        )
        generate_sdf_file(
            model,
            output_path,
            "model.config",
            "gazebo/model.config.jinja",
            template_path=template_path,
        )


def gazebo_world(config, g, model_name):
    template_path = config["templates"]["path"]

    instances = get_all_object_instances(g)
    model = {"instances": instances, "name": model_name}

    output_path = get_output_path(config, "gazebo_models", model_name)
    generate_sdf_file(
        model,
        output_path,
        "model.config",
        "gazebo/model.config.jinja",
        template_path=template_path,
    )
    generate_sdf_file(
        model,
        output_path,
        "model.sdf",
        "gazebo/floorplan.sdf.jinja",
        template_path=template_path,
    )

    output_path = get_output_path(config, "gazebo_worlds")
    generate_sdf_file(
        model,
        output_path,
        "{name}.world".format(name=model_name),
        template_name="gazebo/world.sdf.jinja",
        template_path=template_path,
    )

    output_path = get_output_path(config, "ros_launch")
    generate_launch_file(
        model_name,
        output_path,
        template_name="ros/world.launch.jinja",
        template_path=template_path,
    )


def tasks(config, g, model_name):
    output_path = get_output_path(config, "tasks", model_name)
    inset_width = config["transformations"]["tasks"]["inset_width"]

    tasks = get_all_disinfection_tasks(g, inset_width)
    for task in tasks:
        generate_task_specification(task, output_path)


def get_output_path(config, model_type, model_name=None):
    output_config = config.get("output")
    subfolder = output_config.get(model_type)
    if model_name is None:
        return os.path.join(output_config["base_path"], subfolder)
    else:
        return os.path.join(output_config["base_path"], subfolder, model_name)


@floorplan.command()
@click.argument("configfile", type=click.Path(exists=True, resolve_path=True))
@click.argument("inputs", type=click.Path(exists=True, resolve_path=True))
def generate(configfile, inputs):
    click.echo(click.format_filename(configfile))
    config = load_config_file(configfile)

    g = build_graph_from_directory(inputs)
    model_name = get_floorplan_model_name(g)

    tasks(config, g, model_name)

    door_object_models(config, g)
    gazebo_world(config, g, model_name)


if __name__ == "__main__":
    floorplan()
