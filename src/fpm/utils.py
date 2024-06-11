import os
import tomllib

from jinja2 import Environment, FileSystemLoader


def load_config_file(file_path):
    with open(file_path, "rb") as f:
        data = tomllib.load(f)
    return data


def loader(directory):
    import os
    def load(file):
        with open(os.path.join(directory, file)) as f:
            return f.read()
        return ""
    return load


def load_template(template_name, template_folder):
    file_loader = FileSystemLoader(template_folder)
    env = Environment(loader=file_loader)
    return env.get_template(template_name)


def write_sdf_file(data, output_folder, file_name, template_name, template_folder="templates"):

    template = load_template(template_name, template_folder)
    
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    output = template.render(data=data, trim_blocks=True, lstrip_blocks=True)
    
    file_path = os.path.join(output_folder, file_name) 
    with open(file_path, "w") as f:
        f.write(output)
        print("FILE: {path}".format(path=file_path))
