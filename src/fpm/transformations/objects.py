#!/usr/bin/env python

from rdflib import RDF

from fpm.transformations.sdf import (
    get_sdf_geometry, 
    get_sdf_intertia, 
    get_sdf_pose_from_transformation_matrix,
    get_sdf_joint_type,
    get_sdf_axis_of_rotation,
)

from fpm.constants import *
from fpm.graph import prefixed, get_transformation_matrix_wrt_frame, get_floorplan_model_name


def get_link_information(g, my_object, object_frame):
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

        # Get the frame for the link
        link_frame = g.value(link, OBJ["link-frame"])
        
        T = get_transformation_matrix_wrt_frame(g, link_frame, object_frame)
        pose_coordinates = get_sdf_pose_from_transformation_matrix(T)

        return {
            "pose": pose_coordinates,
            "inertial": sdf_inertia,
            "collision": sdf_physics_geometry,
            "visual": sdf_visual_geometry,
            "name" : prefixed(g, simplices_link),
            "material": material.toPython()
        }

def get_joint_information(g, joint, object_frame):
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
    return {
        "name": prefixed(g, joint),
        "type": joint_type,
        "axis": joint_axis,
        "pose": pose_coordinates,
        "parent": prefixed(g, parent),
        "children": children,
        "limits": limits,
    }


def get_object_model(g, my_object):
    joint_list = []
    link_list = []

    object_frame = g.value(my_object, OBJ["object-frame"])
    
    # Collect the link information
    link_info = get_link_information(g, my_object, object_frame)
    link_list.append(link_info)
            
    # If the object is a kinematic chain, collect the joint information
    if OBJ["ObjectWithKinematicChain"] in g.objects(my_object, RDF.type):
        
        kin_chain = g.value(my_object, OBJ["kinematic-chain"])
        for _, _, joint in g.triples((kin_chain, KIN["joints"], None)):
            joint_info = get_joint_information(g, joint, object_frame)
            joint_list.append(joint_info)
    # Build a dictionary with all the data for jinja
    return {
        "name": prefixed(g, my_object),
        "static": "false",
        "links": link_list,
        "joints": joint_list
    }
    

def get_object_instance(g, instance):
    #  Name of the object
    of_obj = g.value(instance, OBJ["of-object"])

    # ID of the frame
    frame = g.value(instance, OBJ["frame"])
    
    # Query for the pose path from the object instance to the world frame
    world_frame_tag = g.value(predicate=RDF.type, object=OBJ["WorldFrame"])
    world_frame = g.value(world_frame_tag, OBJ["frame"])
    
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
    return {
        "pose": pose_coordinates,
        "static": "false",
        "name": prefixed(g, of_obj)[5:],
        "instance_name": prefixed(g, instance)[5:],
        "start_joint_states": start_joint_states
    }

def get_all_object_models(g):
    objects = list()
    for my_object, _, _ in g.triples((None, RDF.type, OBJ["Object"])):
        my_object_tree = get_object_model(g, my_object)
        objects.append(my_object_tree)
    return objects

def get_all_object_instances(g):
    instances = list()
    for instance, _, _ in g.triples((None, RDF.type, OBJ["ObjectInstance"])):
        obj_instance = get_object_instance(g, instance)
        instances.append(obj_instance)
    return instances
