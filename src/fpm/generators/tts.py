import numpy as np

from fpm.graph import get_3d_structure
from fpm.utils import render_model_template, get_output_path


def get_dim_and_center(element):
    points = np.array(element.get("vertices"))
    min_values = np.min(points, axis=0)
    max_values = np.max(points, axis=0)
    dims = np.abs(max_values - min_values)
    center = min_values + dims / 2
    return {"id": element.get("name"), "center": center, "dimensions": dims}


def gen_tts_wall_description(g, base_path, **kwargs):
    template_path = kwargs.get("template_path")
    output_path = get_output_path(base_path, "tts")

    entryways_elements = get_3d_structure(g, "Entryway")
    window_elements = get_3d_structure(g, "Window")
    openings = dict()
    for entryway in entryways_elements:
        voids = entryway.get("voids")
        e = get_dim_and_center(entryway)
        for w in voids:
            openings.setdefault(w, list()).append(e)

    for window in window_elements:
        voids = window.get("voids")
        e = get_dim_and_center(window)
        openings.setdefault(voids, list()).append(e)

    wall_elements = get_3d_structure(g, "Wall")
    model = list()
    for wall in wall_elements:
        w = get_dim_and_center(wall)
        w["cutouts"] = openings.get(wall.get("name"))
        print(w)
        model.append(w)

    render_model_template(
        model,
        output_path,
        "walls.json",
        "tts/walls.json.jinja",
        template_path,
    )


def gen_tts_task_description(**kwargs):
    pass
