from fpm.utils import load_template, save_file, get_output_path


def generate_launch_file(model_name, output_path, file_name, **custom_args):
    template_name = custom_args.get("template_name", "world.launch.jinja")
    template_path = custom_args.get("template_path")
    template = load_template(template_name, template_path)

    ros_pkg = custom_args.get("ros_pkg", "floorplan_models")

    output = template.render(ros_pkg=ros_pkg, model_name=model_name)

    save_file(output_path, file_name, output)


def gazebo_world_launch(model_name, base_path, **kwargs):
    template_path = kwargs.get("template_path")
    output_path = get_output_path(base_path, "ros/launch")

    if kwargs.get("ros_version", "ros2") == "ros2":
        file_name = "{name}.ros2.launch".format(name=model_name)
        template_name = "ros/world.ros2.launch.jinja"
    else:
        file_name = "{name}.ros1.launch".format(name=model_name)
        template_name = "ros/world.ros1.launch.jinja"

    generate_launch_file(
        model_name,
        output_path,
        file_name,
        template_name=template_name,
        template_path=template_path,
        **kwargs,
    )
