from fpm.utils import load_template, save_file


def write_sdf_file(data, output_folder, file_name, template_name, template_folder="templates"):

    template = load_template(template_name, template_folder)

    output = template.render(data=data, trim_blocks=True, lstrip_blocks=True)

    save_file(output_folder, file_name, output)
