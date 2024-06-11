#!/usr/bin/env python

import sys, os, configparser
import rdflib
from rdflib import RDF
import json
from pyld import jsonld
from pprint import pprint

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as Pol

from helpers.helpers import (
    loader, 
    prefixed, 
    get_transformation_matrix_wrt_frame
)
from helpers.sdf import (
    get_sdf_geometry, 
    get_sdf_intertia, 
    get_sdf_pose_from_transformation_matrix,
    get_sdf_joint_type,
    get_sdf_axis_of_rotation,
    write_object_model_sdf,
    write_world_model_sdf
)
from helpers.constants import ROOT_PATH

from helpers.constants import *

if __name__ == "__main__":

    # Read folder where composable models are located and other configs
    argv = sys.argv
    input_folder = argv[1]

    # Read config file and set properties
    config = configparser.ConfigParser()
    config.read(os.path.join(ROOT_PATH, 'setup.cfg'))
    model_config = config["models"]
    DEBUG = config["dev"].getboolean('debug')
    output_folder = model_config.get("gazebo_models_location") if model_config.getboolean('save_to_gazebo') else model_config.get("output_folder")
    worlds_output_path = config["worlds"]["output"]
    
    # Build the graph by reading all composable models in the input folder
    load = loader("")
    g = rdflib.Graph()
    for (dirpath, dirnames, filenames) in os.walk(input_folder):
        for filename in filenames:
            #filenames_array.append(os.path.join(dirpath, filename))
            g.parse(os.path.join(dirpath, filename), format="json-ld")
    
    fp_model_name = ''
    for floorplan in g.subjects(RDF.type, FP["FloorPlan"]):
        fp_model_name = prefixed(g, floorplan).split('floorplan:')[1]

    for my_object, _, _ in g.triples((None, RDF.type, OBJ["Object"])):
        joint_list = []
        link_list = []

        object_frame = g.value(my_object, OBJ["object-frame"])
        
        # Collect the link information
        for _, _, link in g.triples((my_object, OBJ["object-links"], None)):

            gazebo_representation = g.value(predicate=GZB["gz-link"], object=link)
            
            # Get the objects for the link geometry
            visual = g.value(gazebo_representation, GZB["visual"])
            visual_link = g.value(visual, OBJ["polytope"])
            collision = g.value(gazebo_representation, GZB["collision"])
            physics_link = g.value(collision, OBJ["polytope"])
            inertia = g.value(gazebo_representation, GZB["inertia"])
            material = g.value(gazebo_representation, GZB["material"])
            simplices_link = g.value(visual, OBJ["link"])

            # Get the sdf geometry description
            sdf_visual_geometry = get_sdf_geometry(g, visual_link)
            sdf_physics_geometry = get_sdf_geometry(g, physics_link)
            
            # Get the sdf inertia description
            sdf_inertia = get_sdf_intertia(g, inertia)
            # for inertia in g.subjects(RBD["of-body"], simplices_link):
            #     sdf_inertia = get_sdf_intertia(g, inertia)

            # Get the frame for the link
            link_frame = g.value(link, OBJ["link-frame"])
            
            T = get_transformation_matrix_wrt_frame(g, link_frame, object_frame)
            pose_coordinates = get_sdf_pose_from_transformation_matrix(T)

            if (DEBUG):
                print(sdf_visual_geometry, sdf_physics_geometry, sdf_inertia, pose_coordinates)

            link_list.append({
                "pose": pose_coordinates,
                "inertial": sdf_inertia,
                "collision": sdf_physics_geometry,
                "visual": sdf_visual_geometry,
                "name" : prefixed(g, simplices_link),
                "material": material.toPython()
            })
                
        # If the object is a kinematic chain, collect the joint information
        if OBJ["ObjectWithKinematicChain"] in g.objects(my_object, RDF.type):
            
            kin_chain = g.value(my_object, OBJ["kinematic-chain"])
            for _, _, joint in g.triples((kin_chain, KIN["joints"], None)):
                
                # determine axis of joint
                joint_axis = get_sdf_axis_of_rotation(g, joint)
                
                # determine type of joint
                joint_type = get_sdf_joint_type(g, joint)

                # Get parent and children bodies
                joint_with_tree = g.value(predicate=OBJ["joint-without-tree"], object=joint)
                parent = g.value(joint_with_tree, OBJ["parent"])
                children = [prefixed(g, c) for _, _, c in g.triples((joint_with_tree , OBJ["children"], None))]

                # Determine the joint frame for the pose
                common_axis = g.value(joint, KIN["common-axis"])
                joint_frame = None
                for _, _, vector in g.triples((common_axis, GEOM["lines"], None)):
                    for p in g.predicates(None, vector):

                        # If the vector is not related to the parent then ignore this vector
                        if len([p for p in g.predicates(parent, vector)]) == 0:
                            continue
                        
                        subject = g.value(predicate=p, object=vector)
                        for _, _, _ in g.triples((subject, RDF.type, GEO["Frame"])):
                            joint_frame = subject

                # Determine frame of reference and pose wrt object frame
                T = get_transformation_matrix_wrt_frame(g, joint_frame, object_frame)
                pose_coordinates = get_sdf_pose_from_transformation_matrix(T)

                limits = {"upper": None, "lower": None}
                for position, pre, _ in g.triples((None, KSTATE["of-joint"], joint)):
                    for p in g.objects(position, RDF.type):
                        if p == OBJ["JointLowerLimit"]:
                            limits["lower"] = g.value(position, QUDT["value"]).toPython()
                        elif p == OBJ["JointUpperLimit"]:
                            limits["upper"] = g.value(position, QUDT["value"]).toPython()
       
                # Build a dictionary with all the data for jinja
                joint_list.append({
                    "name": prefixed(g, joint),
                    "type": joint_type,
                    "axis": joint_axis,
                    "pose": pose_coordinates,
                    "parent": prefixed(g, parent),
                    "children": children,
                    "limits": limits,
                })

        # Build a dictionary with all the data for jinja
        my_object_tree = {
            "name": prefixed(g, my_object),
            "static": "false",
            "links": link_list,
            "joints": joint_list
        }
        
        if DEBUG:
            pprint(my_object_tree)

        # Write the sdf model
        write_object_model_sdf(my_object_tree, output_folder)

    # Querie for the pose path from the object instance to the world frame
    world_frame_tag = g.value(predicate=RDF.type, object=OBJ["WorldFrame"])
    world_frame = g.value(world_frame_tag, OBJ["frame"])

    data = {
        "instances": [],
        "world_name": None,
        "model_name": None
    }

    # Go through the object instances
    for instance, _, _ in g.triples((None, RDF.type, OBJ["ObjectInstance"])):
        
        # Get the world name
        world = g.value(instance, OBJ["world"])

        #  Name of the object
        of_obj = g.value(instance, OBJ["of-object"])

        # ID of the frame
        frame = g.value(instance, OBJ["frame"])
        
        # Get the transfomation from the instance pose frame and the world frame
        T = get_transformation_matrix_wrt_frame(g, frame, world_frame)
        pose_coordinates = get_sdf_pose_from_transformation_matrix(T)

        state = g.value(instance, ST["start-state"])
        start_joint_states = []

        # If the instance has a state, then include the initial state plugin
        if state != None:
            for joint_state, _, _ in g.triples((None, ST["state"], state)):

                if not ST["JointState"] in g.value(joint_state, RDF.type):
                    continue
                    
                joint = g.value(joint_state, ST["joint"])
                joint_name = prefixed(g, joint)

                pose = g.value(joint_state, ST["pose"])
                value = g.value(pose, QUDT["value"]).toPython()

                start_joint_states.append({
                    "joint": joint_name,
                    "position": value
                })

        # Build a dictionary for the instance for the jinja template
        instance = {
            "pose": pose_coordinates,
            "static": "false",
            "name": prefixed(g, of_obj)[5:],
            "instance_name": prefixed(g, instance)[5:],
            "start_joint_states": start_joint_states
        }

        data["instances"].append(instance)
        data["model_name"] = prefixed(g, world)[10:]
        data["world_name"] = "{}".format(prefixed(g, world))

    # Build and write the sdf world
    write_world_model_sdf(data, worlds_output_path)
