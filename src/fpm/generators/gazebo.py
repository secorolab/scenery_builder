from fpm.utils import load_template, save_file


def generate_sdf_file(
    model, output_folder, file_name, template_name, template_path=None
):

    template = load_template(template_name, template_path)

    output = template.render(model=model, trim_blocks=True, lstrip_blocks=True)

    save_file(output_folder, file_name, output)
