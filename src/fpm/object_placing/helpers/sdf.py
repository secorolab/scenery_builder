import numpy as np
from rdflib import RDF
from fpm.constants import *
from jinja2 import Environment, FileSystemLoader
import os

def get_sdf_geometry(g, polytope):

    if (polytope, RDF.type, POLY["CuboidWithSize"]):
        x = g.value(polytope, POLY["x-size"])
        y = g.value(polytope, POLY["y-size"])
        z = g.value(polytope, POLY["z-size"])

        return {
            "type": "box",
            "size": "{x} {y} {z}".format(x=x, y=y, z=z)
        }
    
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

    tx = np.arctan2(T[2,1], T[2, 2])
    ty = np.arctan2(-T[2,0], np.sqrt(T[2,1]**2 + T[2,2]**2))
    tz = np.arctan2(T[1,0], T[0,0])

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

def write_object_model_sdf(data, output_folder):

    # TODO Fix this path
    file_loader = FileSystemLoader(os.path.join("../../../",'templates/object_placing'))
    env = Environment(loader=file_loader)
    
    name_without_id = data["name"][5:]
    full_path = os.path.join(output_folder, name_without_id)

    if not os.path.exists(full_path):
        os.makedirs(full_path)
    template = env.get_template('model.sdf.jinja')
    output = template.render(data=data, trim_blocks=True, lstrip_blocks=True)

    with open(os.path.join(full_path, "model.sdf"), "w") as f:
        f.write(output)
        print("{name} MODEL FILE: {path}".format(name=name_without_id, path=os.path.join(full_path, "model.sdf")))

    template = env.get_template('model.config.jinja')
    output = template.render(data=data, trim_blocks=True, lstrip_blocks=True)

    with open(os.path.join(full_path, "model.config".format(name=name_without_id)), "w") as f:
        f.write(output)
        print("{name} CONFIG FILE: {path}".format(name=name_without_id, path=os.path.join(full_path, "{name}.config".format(name=name_without_id))))

def write_world_model_sdf(data, output_folder):
    
    # TODO Fix this path
    file_loader = FileSystemLoader(os.path.join("../../../",'templates/object_placing'))
    env = Environment(loader=file_loader)

    name_without_id = data["world_name"][10:]
    
    full_path = os.path.join(output_folder)
    if not os.path.exists(full_path):
        os.makedirs(full_path)

    template = env.get_template('world.sdf.jinja')
    output = template.render(data=data, trim_blocks=True, lstrip_blocks=True)

    # TODO Fix this path
    with open(os.path.join(full_path, "{name_without_id}.world".format(name_without_id=name_without_id)), "w") as f:
        f.write(output)
        print("{name} WORLD FILE: {path}".format(name=name_without_id, path=os.path.join(full_path, "{name_without_id}.world").format(name_without_id=name_without_id)))
