import rdflib
import os
from pathlib import Path

# FloorPlan metamodels
FP = rdflib.Namespace("https://hbrs-sesame.github.io/metamodels/floorplan#")
OBJ = rdflib.Namespace("https://hbrs-sesame.github.io/metamodels/object#")
ST = rdflib.Namespace("https://hbrs-sesame.github.io/metamodels/state#")

# Kinematic chain metamodels
KIN = rdflib.Namespace("https://comp-rob2b.github.io/metamodels/kinematic-chain/structural-entities#")
KSTATE = rdflib.Namespace("https://comp-rob2b.github.io/metamodels/kinematic-chain/state#")

# Rigid Body Dynamic metamodels
RBD = rdflib.Namespace("https://comp-rob2b.github.io/metamodels/newtonian-rigid-body-dynamics/structural-entities#")

# Geometry metamodels
GEOM = rdflib.Namespace("https://comp-rob2b.github.io/metamodels/geometry/spatial-relations#")
GEO = rdflib.Namespace("https://comp-rob2b.github.io/metamodels/geometry/structural-entities#")
POLY = rdflib.Namespace("https://hbrs-sesame.github.io/metamodels/polytope#")
QUDT = rdflib.Namespace("http://qudt.org/schema/qudt/")
QUDT_VOCAB = rdflib.Namespace("http://qudt.org/vocab/unit/")
COORD = rdflib.Namespace("https://comp-rob2b.github.io/metamodels/geometry/coordinates#")
COORD_EXT = rdflib.Namespace("https://hbrs-sesame.github.io/metamodels/coordinates#")

# simulator metamodel
GZB = rdflib.Namespace("https://hbrs-sesame.github.io/metamodels/gazebo#")

ROOT_PATH = Path(os.path.dirname(os.path.abspath(__file__))).parent