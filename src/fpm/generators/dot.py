import subprocess

from fpm.graph import get_floorplan_elements, get_frame_tree
from fpm.utils import load_template, save_file


def visualize_frame_tree(g, floorplan_elements, **kwargs):
    import os

    output_path = kwargs.get("output_path")
    print(kwargs)
    element_poses = get_floorplan_elements(g, floorplan_elements)
    frames = get_frame_tree(g, element_poses)

    template = load_template("frame-tree.dot.jinja")

    file_name = "frame-tree"
    frames_gv = "{:s}.gv".format(file_name)
    frames_pdf = "{:s}.pdf".format(file_name)
    contents = template.render(frames=frames)
    save_file(output_path, frames_gv, contents)

    dot_file_path = os.path.join(output_path, frames_gv)
    pdf_file_path = os.path.join(output_path, frames_pdf)
    cmd = ["dot", "-Tpdf", dot_file_path, "-o", pdf_file_path]
    subprocess.Popen(cmd).communicate()
