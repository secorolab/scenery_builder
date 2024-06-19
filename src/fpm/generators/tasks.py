import yaml

from fpm.utils import save_file


def generate_task_specification(model, output_path, **custom_args):
    file_name = "{}_task.yaml".format(model.get("id"))
    save_file(output_path, file_name, model)
