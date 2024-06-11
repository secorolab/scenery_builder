#!/usr/bin/env python

# SPDX-License-Identifier: LGPL-3.0-or-later

import rdflib
import json
from pyld import jsonld
from pprint import pprint

def loader(directory):
    import os
    def load(file):
        with open(os.path.join(directory, file)) as f:
            return f.read()
        return ""
    return load

if __name__ == "__main__":
    # 1. Construct the RDF graph
    g = rdflib.Graph()
    g.parse("models/skeleton.json", format="json-ld")
    g.parse("models/shape.json", format="json-ld")
    g.parse("models/spatial_relations.json", format="json-ld")
    g.parse("models/floorplan.json", format="json-ld")
    g.parse("models/coordinate.json", format="json-ld")

    load = loader("")

    # 2. Run the SPARQL query (graph-to-graph)
    aux = load("queries/test.rq")
    res = g.query(aux)

    # 3. Transform the PyLD
    res_json = json.loads(res.serialize(format="json-ld"))
    context = [
        "https://comp-rob2b.github.io/metamodels/geometry/structural-entities.json",
        "https://comp-rob2b.github.io/metamodels/geometry/spatial-relations.json",
        "https://comp-rob2b.github.io/metamodels/geometry/coordinates.json",
        "https://comp-rob2b.github.io/metamodels/qudt.json",
        {
            "@base": "http://exsce-floorplan.org/",
            "fp" : "http://exsce-floorplan.org/",
            "xsd": "http://www.w3.org/2001/XMLSchema#",
            "Polygon" : "fp:Polygon",
            "Space" : "fp:Space",
            "points": {
                "@id": "fp:points",
                "@container": "@list",
                "@type": "@id"
            },
            "shape" : {
                "@id" : "fp:shape",
                "@type" : "@id"
            }
        }
    ]

    model = {"@context": context, "@graph": res_json}

    # 4. Run PyLD's framing algorithm (graph-to-tree)
    frame = json.loads(load("templates/shape_frame.json"))
    model_framed = jsonld.frame(model, frame)

    print(model_framed)
    # 5. Serialize launch configuration (to be used by other tools)
    with open("output/res_frame.json", "w") as file:
        json.dump(model_framed, file, indent=4)

    with open("output/res_graph.json", "w") as file:
        json.dump(model, file, indent=4)
