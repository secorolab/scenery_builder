import logging

from fpm.graph import get_floorplan_model_name, get_internal_walls
from fpm.utils import save_file, load_template, get_output_path

logger = logging.getLogger("floorplan.generators.polyline")
logger.setLevel(logging.DEBUG)


def generate_polyline_representation(
    g, output_path, template_name="polyline.poly.jinja", template_path=None, **kwargs
):
    logger.info("Generating polyline representation...")
    model_name = get_floorplan_model_name(g)
    file_name = kwargs.get("file_name", "{}.poly".format(model_name))
    wall_planes_by_space = get_internal_walls(g)

    template = load_template(template_name, template_path)
    output = template.render(
        model=wall_planes_by_space, trim_blocks=True, lstrip_blocks=True
    )

    save_file(output_path, file_name, output)


def get_polyline_floorplan(g, base_path, **kwargs):
    output_path = get_output_path(base_path, "polyline")
    generate_polyline_representation(g, output_path, **kwargs)
