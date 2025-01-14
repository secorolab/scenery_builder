import os
import tomllib

import yaml

import numpy as np

from jinja2 import Environment, FileSystemLoader, PackageLoader


def load_config_file(file_path):
    with open(file_path, "rb") as f:
        data = tomllib.load(f)
    return data


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
    else:
        with open(output_file, "w") as f:
            f.write(contents)

    print("Generated {path}".format(path=output_file))


def build_transformation_matrix(x, y, z, alpha):

    c = np.cos
    s = np.sin

    a = np.deg2rad(alpha)
    t = np.array([[x], [y], [z], [1]])
    # fmt: off
    R = np.array([
        [c(a), -s(a), 0],
        [s(a), c(a), 0],
        [0, 0, 1],
        [0, 0, 0]]
    )
    # fmt: on

    return np.hstack((R, t))
