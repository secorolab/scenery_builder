import os
import tomllib
import logging

import yaml
import json

import numpy as np

from jinja2 import Environment, FileSystemLoader, PackageLoader

logger = logging.getLogger("floorplan.utils")
logger.setLevel(logging.DEBUG)


def load_config_file(file_path):
    with open(file_path, "rb") as f:
        data = tomllib.load(f)
    return data


def render_model_template(
    model, output_folder, file_name, template_name, template_path=None
):
    template = load_template(template_name, template_path)

    output = template.render(model=model, trim_blocks=True, lstrip_blocks=True)
    if file_name.endswith(".json"):
        output = json.loads(output)
    elif file_name.endswith(".yaml"):
        output = yaml.safe_load(output)

    return save_file(output_folder, file_name, output)


def load_template(template_name, template_folder=None):
    if template_folder is None:
        loader = PackageLoader("fpm")
    else:
        loader = FileSystemLoader(template_folder)
    env = Environment(loader=loader)
    return env.get_template(template_name)


def save_file(output_path, file_name, contents):
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    base_name, ext = os.path.splitext(file_name)
    output_file = os.path.abspath(os.path.join(output_path, file_name))

    if ext in [".yaml"]:
        with open(output_file, "w") as f:
            yaml.dump(contents, f, default_flow_style=None)
    elif ext == ".json":
        with open(output_file, "w") as f:
            json.dump(contents, f, indent=4)
    elif ext in [".pgm", ".jpg"]:
        contents.save(output_file, quality=100)
    else:
        with open(output_file, "w") as f:
            f.write(contents)

    logger.info("Generated {path}".format(path=output_file))
    return output_file


def build_transformation_matrix(x, y, z, alpha=None, beta=0.0, gamma=0.0, **kwargs):

    t = np.array([[x], [y], [z], [1]])
    # fmt: off
    if alpha is not None:
        R = np.array([
        [np.cos(alpha), -np.sin(alpha), 0],
        [np.sin(alpha), np.cos(alpha), 0],
        [0, 0, 1],
        [0, 0, 0]]
        )
    else:
        cosx = kwargs.get("direction-cosine-x", [1.0, 0.0, 0.0])
        cosz = kwargs.get("direction-cosine-z", [0.0, 0.0, 1.0])
        cosy = kwargs.get("direction-cosine-y", np.cross(cosz, cosx))
        R = np.vstack((np.array([cosx, cosy, cosz]).T, [0.0] *3))

    # fmt: on

    return np.hstack((R, t))


def get_output_path(base_path, subfolder, model_name=None):
    if model_name is None:
        return os.path.join(base_path, subfolder)
    else:
        return os.path.join(base_path, subfolder, model_name)
