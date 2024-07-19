from fpm.utils import load_template, save_file


def generate_launch_file(model_name, output_path, file_name, **custom_args):
    template_name = custom_args.get("template_name", "world.launch.jinja")
    template_path = custom_args.get("template_path")
    template = load_template(template_name, template_path)

    ros_pkg = custom_args.get("ros_pkg", "floorplan_models")

    output = template.render(pkg_path=ros_pkg, model_name=model_name)

    save_file(output_path, file_name, output)
