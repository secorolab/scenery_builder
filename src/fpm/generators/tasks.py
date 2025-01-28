import yaml
from fpm.transformations.tasks import get_all_disinfection_tasks

from fpm.utils import save_file, get_output_path


def generate_task_specification(model, output_path, **custom_args):
    file_name = "{}_task.yaml".format(model.get("id"))
    save_file(output_path, file_name, model)


def tasks(g, base_path, **kwargs):
    output_path = get_output_path(base_path, "tasks")
    inset_width = kwargs.get("waypoint_dist_to_corner")

    tasks = get_all_disinfection_tasks(g, inset_width)
    for task in tasks:
        generate_task_specification(task, output_path)
