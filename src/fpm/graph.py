import os
import glob

import rdflib


def build_graph_from_directory(input_folder):
    # Build the graph by reading all composable models in the input folder
    g = rdflib.Graph()
    input_models = glob.glob(os.path.join(input_folder, "*.json"))
    for file_path in input_models:
        g.parse(file_path, format="json-ld")

    return g
