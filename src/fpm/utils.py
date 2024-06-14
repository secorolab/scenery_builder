import os
import tomllib

import numpy as np

from jinja2 import Environment, FileSystemLoader


def load_config_file(file_path):
    with open(file_path, "rb") as f:
        data = tomllib.load(f)
    return data


def load_template(template_name, template_folder):
    file_loader = FileSystemLoader(template_folder)
    env = Environment(loader=file_loader)
    return env.get_template(template_name)

def save_file(output_path, file_name, contents):
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    output_file = os.path.abspath(os.path.join(output_path, file_name))

    with open(output_file, "w") as f:
        f.write(contents)
        print("Generated {path}".format(path=output_file))


def build_transformation_matrix(x, y, z, theta):
    
    c = np.cos 
    s = np.sin

    # TODO Task generation seems to use this and expect radians
    # a = np.deg2rad(theta)
    t = np.array([[x], [y], [z], [1]])
    R = np.array([
        [c(theta), -s(theta), 0],
        [s(theta), c(theta), 0],
        [0, 0, 1],
        [0, 0, 0]]
    )

    return np.hstack((R, t))
