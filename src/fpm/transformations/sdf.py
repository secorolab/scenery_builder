import numpy as np
from rdflib import RDF
from fpm.constants import *


def get_sdf_geometry(g, polytope):

    if (polytope, RDF.type, POLY["CuboidWithSize"]):
        x = g.value(polytope, POLY["x-size"])
        y = g.value(polytope, POLY["y-size"])
        z = g.value(polytope, POLY["z-size"])

        return {"type": "box", "size": "{x} {y} {z}".format(x=x, y=y, z=z)}


def get_sdf_intertia(g, inertia):
    sdf_inertia = {}

    sdf_inertia["mass"] = g.value(inertia, RBD["mass"]).toPython()
    sdf_inertia["inertia"] = {}
    sdf_inertia["inertia"]["ixx"] = g.value(inertia, RBD["xx"]).toPython()
    sdf_inertia["inertia"]["iyy"] = g.value(inertia, RBD["yy"]).toPython()
    sdf_inertia["inertia"]["izz"] = g.value(inertia, RBD["zz"]).toPython()

    return sdf_inertia


def get_sdf_pose_from_transformation_matrix(T):

    x = T[0, 3]
    y = T[1, 3]
    z = T[2, 3]

    tx = np.arctan2(T[2, 1], T[2, 2])
    ty = np.arctan2(-T[2, 0], np.sqrt(T[2, 1] ** 2 + T[2, 2] ** 2))
    tz = np.arctan2(T[1, 0], T[0, 0])

    return "{x} {y} {z} {tx} {ty} {tz}".format(x=x, y=y, z=z, tx=tx, ty=ty, tz=tz)


def get_sdf_joint_type(g, joint):

    for _, t, o in g.triples((joint, None, None)):
        if o == KIN["RevoluteJoint"]:
            return "revolute"
        elif o == OBJ["PrismaticJoint"]:
            return "prismatic"
    else:
        return "fixed"


def get_sdf_axis_of_rotation(g, joint):

    common_axis = g.value(joint, KIN["common-axis"])

    if common_axis == None:
        # Default value for unexpressed common axis in sdf
        return "0 0 1"

    x = 0
    y = 0
    z = 0

    for _, _, line in g.triples((common_axis, GEOM["lines"], None)):
        for _, predicate, _ in g.triples((None, None, line)):
            if predicate == GEO["vector-x"]:
                x = 1
            elif predicate == GEO["vector-y"]:
                y = 1
            elif predicate == GEO["vector-z"]:
                z = 1

    return "{x} {y} {z}".format(x=x, y=y, z=z)
