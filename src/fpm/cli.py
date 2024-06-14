import os
import click 

from fpm.utils import load_config_file
from fpm.graph import build_graph_from_directory, get_floorplan_model_name
from fpm.generators.ros import generate_launch_file
from fpm.generators.gazebo import generate_sdf_file
from fpm.generators.tasks import generate_task_specification
from fpm.transformations.tasks import get_all_disinfection_tasks

@click.group()
def floorplan():
    pass

def gazebo_world(config, model):
    models_output_path = config["models"]["output"]
    worlds_output_path = config["worlds"]["output"]
    launch_output_path = config["launch"]["output"]
    template_path = config["templates"]["path"]

    model_name = model.get("name")
    # Generate Gazebo models and ROS launch files
    output_path = os.path.join(models_output_path, model_name)

    # TODO Fix hardcoded paths
    generate_sdf_file(model, output_path,
                   "model.config",
                   "gazebo/model.config.jinja",
                    # template_path="../../../templates/gazebo"
                    template_path=template_path
                   )

    generate_sdf_file(model, output_path,
                   "model.sdf",
                   "gazebo/floorplan.sdf.jinja",
                    # template_path="../../../templates/gazebo"
                    template_path=template_path
                   )

    generate_sdf_file(model, worlds_output_path,
                   "{name}.world".format(name=model_name),
                   template_name="gazebo/world.sdf.jinja",
                    # template_path="../../../templates/gazebo"
                    template_path=template_path
                   )
    generate_launch_file(model_name, launch_output_path, 
                         template_name="ros/world.launch.jinja",
                        #  template_path="../../../templates/ros"
                         template_path=template_path
                         )


def tasks(config, g, model_name):
    output_path = config["points"]["output"]
    inset_width = config["inset"]["width"]

    tasks = get_all_disinfection_tasks(g, inset_width)
    directory = os.path.join(output_path, model_name)
    for task in tasks:
        generate_task_specification(task, directory)

@floorplan.command()
@click.argument("configfile", type=click.Path(exists=True, resolve_path=True))
@click.argument("inputs", type=click.Path(exists=True, resolve_path=True))
def generate(configfile, inputs):
    click.echo(click.format_filename(configfile))
    config = load_config_file(configfile)

    g = build_graph_from_directory(inputs)
    model_name = get_floorplan_model_name(g)

    tasks(config, g, model_name)

    model = {"name": model_name}
    gazebo_world(config, model)

if __name__=="__main__":
    floorplan()