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


def door_object_models(g, base_path, **kwargs):
    template_path = kwargs.get("template_path")

    object_models = get_all_object_models(g)

    for model in object_models:
        model_name = model["name"][5:]
        output_path = get_output_path(base_path, "gazebo/models", model_name)
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


def gazebo_floorplan_model(model_name, base_path, **kwargs):
    template_path = kwargs.get("template_path")
    model = {"name": model_name}
    output_path = get_output_path(base_path, "gazebo/models", model_name)
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


def gazebo_world_model(g, model_name, base_path, **kwargs):
    template_path = kwargs.get("template_path")
    instances = get_all_object_instances(g)
    model = {"instances": instances, "name": model_name}

    output_path = get_output_path(base_path, "gazebo/worlds")
    generate_sdf_file(
        model,
        output_path,
        "{name}.world".format(name=model_name),
        template_name="gazebo/world.sdf.jinja",
        template_path=template_path,
    )


def gazebo_world_launch(model_name, base_path, **kwargs):
    template_path = kwargs.get("template_path")
    output_path = get_output_path(base_path, "ros/launch")
    generate_launch_file(
        model_name,
        output_path,
        template_name="ros/world.launch.jinja",
        template_path=template_path,
    )


def gazebo_world(g, model_name, base_path, **kwargs):

    gazebo_floorplan_model(model_name, base_path, **kwargs)
    gazebo_world_model(g, model_name, base_path, **kwargs)
    gazebo_world_launch(model_name, base_path, **kwargs)


def tasks(g, base_path, config, **kwargs):
    output_path = get_output_path(base_path, "tasks")
    inset_width = config["tasks"]["inset_width"]

    tasks = get_all_disinfection_tasks(g, inset_width)
    for task in tasks:
        generate_task_specification(task, output_path)


def get_output_path(base_path, subfolder, model_name=None):
    if model_name is None:
        return os.path.join(base_path, subfolder)
    else:
        return os.path.join(base_path, subfolder, model_name)


@floorplan.command()
@click.argument("configfile", type=click.Path(exists=True, resolve_path=True))
@click.option(
    "--inputs",
    "-i",
    type=click.Path(exists=True, resolve_path=True),
    required=True,
    multiple=True,
)
@click.option(
    "--output-path",
    type=click.Path(exists=True, resolve_path=True),
    default=os.path.join("."),
)
@click.option(
    "--templates",
    type=click.Path(exists=True, resolve_path=True),
    default=os.path.join("."),
)
def generate(configfile, inputs, output_path, **kwargs):
    config = load_config_file(configfile)

    g = build_graph_from_directory(inputs)
    model_name = get_floorplan_model_name(g)

    base_path = os.path.join(output_path, model_name)

    tasks(g, base_path, config)

    door_object_models(g, base_path, **kwargs)
    gazebo_world(g, model_name, base_path, **kwargs)


if __name__ == "__main__":
    floorplan()
