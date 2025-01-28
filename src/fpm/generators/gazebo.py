from fpm.generators.ros import gazebo_world_launch
from fpm.transformations.objects import get_all_object_models, get_all_object_instances
from fpm.utils import load_template, save_file, get_output_path


def generate_sdf_file(
    model, output_folder, file_name, template_name, template_path=None
):

    template = load_template(template_name, template_path)

    output = template.render(model=model, trim_blocks=True, lstrip_blocks=True)

    save_file(output_folder, file_name, output)


def gazebo_world(g, model_name, base_path, **kwargs):

    gazebo_floorplan_model(model_name, base_path, **kwargs)
    gazebo_world_model(g, model_name, base_path, **kwargs)
    gazebo_world_launch(model_name, base_path, **kwargs)


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
    if kwargs.get("ros_version", "ros2") == "ros2":
        file_name = "{name}.sdf".format(name=model_name)
    else:
        file_name = "{name}.world".format(name=model_name)

    generate_sdf_file(
        model,
        output_path,
        file_name,
        template_name="gazebo/world.sdf.jinja",
        template_path=template_path,
    )
