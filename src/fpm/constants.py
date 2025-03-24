import rdflib
import os
from pathlib import Path

# FloorPlan metamodels
FP = rdflib.Namespace("https://secorolab.github.io/metamodels/floorplan/floorplan#")
FPMODEL = rdflib.Namespace("https://secorolab.github.io/models/floorplan/")
OBJ = rdflib.Namespace("https://secorolab.github.io/metamodels/floorplan/object#")
ST = rdflib.Namespace("https://secorolab.github.io/metamodels/floorplan/state#")

# Kinematic chain metamodels
KIN = rdflib.Namespace(
    "https://comp-rob2b.github.io/metamodels/kinematic-chain/structural-entities#"
)
KSTATE = rdflib.Namespace(
    "https://comp-rob2b.github.io/metamodels/kinematic-chain/state#"
)

# Rigid Body Dynamic metamodels
RBD = rdflib.Namespace(
    "https://comp-rob2b.github.io/metamodels/newtonian-rigid-body-dynamics/structural-entities#"
)

# Geometry metamodels
GEOM = rdflib.Namespace(
    "https://comp-rob2b.github.io/metamodels/geometry/spatial-relations#"
)
GEO = rdflib.Namespace(
    "https://comp-rob2b.github.io/metamodels/geometry/structural-entities#"
)
POLY = rdflib.Namespace("https://secorolab.github.io/metamodels/geometry/polytope#")
QUDT = rdflib.Namespace("https://qudt.org/schema/qudt/")
QUDT_VOCAB = rdflib.Namespace("https://qudt.org/vocab/unit/")
COORD = rdflib.Namespace(
    "https://comp-rob2b.github.io/metamodels/geometry/coordinates#"
)

# simulator metamodel
GZB = rdflib.Namespace("https://secorolab.github.io/metamodels/gazebo#")

ROOT_PATH = Path(os.path.dirname(os.path.abspath(__file__))).parent
