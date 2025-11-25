import json
import os
import logging

import rdflib
from rdflib import Graph, RDF
from rdflib.plugins.sparql import prepareQuery

from fpm.graph import get_list_values, get_list_from_ptr
from fpm.utils import load_template, save_file
from ifcld.interpreters.namespaces import IFC_CONCEPTS

logger = logging.getLogger("floorplan.generators.scenery")
logger.setLevel(logging.DEBUG)


def add_polyhedron_faces(floorplan):
    from itertools import pairwise

    for f in floorplan:
        if "Polyhedron" not in f.get("@type", list()):
            continue
        points = f["points"]
        bottom = points[:4]
        top = points[4:]

        if f["faces"]:
            continue
        f["faces"].append(list(bottom))
        f["faces"].append(list(top))

        bottom.append(bottom[0])
        top.append(top[0])

        for b, t in zip(pairwise(bottom), pairwise(top)):
            p1, p2 = b
            p4, p3 = t
            f["faces"].append([p1, p2, p3, p4])


def generate_fpm_rep_from_rdf(model_path, output_path):
    logger.debug("Output path: %s", output_path)
    model_name = os.path.basename(model_path).lower().replace(".ifc.json", "")

    # RDF graph
    g = Graph()
    g.parse(model_path, format="json-ld")
    g.bind(
        "ifc-model",
        "https://secorolab.github.io/models/{}/ifc/data#".format(model_name),
    )
    g.bind(
        "ifc",
        "https://secorolab.github.io/metamodels/ifc/".format(model_name),
    )

    # Get the FPM context template for this model
    fp_ctx_template = load_template("ifc/fpm-context.json.jinja")
    fpm_ctx = json.loads(fp_ctx_template.render(model_id=model_name))

    # Add FloorPlan node
    logger.debug("Adding floorplan node")
    floorplan = [
        {"@id": model_name, "@type": "FloorPlan"},
        {
            "@id": "world-frame",
            "@type": "Frame",
            "origin": "world-origin",
        },
        {"@id": "world-origin", "@type": ["3D", "Euclidean", "Point"]},
    ]
    save_file(
        output_path,
        "{}.floorplan.fpm.json".format(model_name),
        {"@graph": floorplan, "@context": fpm_ctx},
    )

    logger.info("Transforming IFC local placements...")
    placements = query_ifc_local_placements(g)
    save_file(
        output_path,
        "{}.placement.fpm.json".format(model_name),
        {"@graph": placements, "@context": fpm_ctx},
    )

    logger.info("Transforming IFC walls...")
    walls = query_ifc_walls(g)
    save_file(
        output_path,
        "{}.walls.fpm.json".format(model_name),
        {"@graph": walls, "@context": fpm_ctx},
    )

    logger.info("Transforming IFC doors...")
    doors = query_ifc_doors(g)
    save_file(
        output_path,
        "{}.doors.fpm.json".format(model_name),
        {"@graph": doors, "@context": fpm_ctx},
    )

    logger.info("Transforming IFC spaces...")
    spaces = query_ifc_spaces(g, model_name=model_name)
    save_file(
        output_path,
        "{}.spaces.fpm.json".format(model_name),
        {"@graph": spaces, "@context": fpm_ctx},
    )

    logger.info("Transforming task elements...")
    task_elements = query_ifc_task_elements(g)
    save_file(
        output_path,
        "{}.task.fpm.json".format(model_name),
        {"@graph": task_elements, "@context": fpm_ctx},
    )

    query_ifc_units(g)

    # doc = list()
    # for l in [placements, walls, doors, spaces]:
    #     doc.extend(l)
    #
    # # compacted = jsonld.compact(doc, fpm_ctx.get("@context"))
    # full_doc = dict(**fpm_ctx)
    # full_doc["@graph"] = doc
    #
    # save_file(output_path, "{}.compacted.fpm.json".format(model_name), full_doc)


def get_entity_id(g, e, entity_type="placement"):
    return g.namespace_manager.curie(e).replace("ifc-model:", "{}-".format(entity_type))


def render_ifc_template(template_path, **kwargs):
    template = load_template(template_path)
    content = template.render(**kwargs)
    if kwargs.get("debug"):
        print("\n**\n", content)
    return json.loads(content)


def query_ifc_local_placements(g: Graph):
    placements = list()
    world_frame = list()

    for p in g.subjects(RDF.type, IFC_CONCEPTS["IFCLOCALPLACEMENT"]):
        entity = get_entity_id(g, p)
        e = render_ifc_template(
            "ifc/placement/object-placement.json.jinja", placement_id=entity
        )
        placements.extend(e)

        prt = g.value(p, IFC_CONCEPTS["placementrelto"])
        if prt is not None:
            prt_entity = get_entity_id(g, prt)
            pj = render_ifc_template(
                "ifc/placement/placement-rel-to.json.jinja",
                placement_id=entity,
                ref_placement_id=prt_entity,
            )
        else:
            # TODO Adding world_frame to all local placements,
            #  but this needs to be reviewed as it depends on the geometric context
            pj = render_ifc_template(
                "ifc/placement/placement-rel-to.json.jinja",
                placement_id=entity,
                world_frame=True,
            )
            world_frame.append(pj)
        placements.extend(pj)

        rp = g.value(p, IFC_CONCEPTS["relativeplacement"])
        ap = transform_axis_placement_3d(g, rp, entity)
        placements.extend(ap)

    return placements


def transform_axis_placement_3d(g: Graph, rel_placement, entity):
    placement = list()
    vars = dict(
        placement_id=entity,
        g=g,
        relative_placement=rel_placement,
        IFC_CONCEPTS=IFC_CONCEPTS,
        rdflib=rdflib,
        list=list,
    )

    axis = g.value(rel_placement, IFC_CONCEPTS["axis"])
    if axis is not None:
        a = render_ifc_template("ifc/placement/rel-placement-axis.json.jinja", **vars)
        placement.extend(a)

    refdir = g.value(rel_placement, IFC_CONCEPTS["refdirection"])
    if refdir is not None:
        r = render_ifc_template(
            "ifc/placement/rel-placement-refdirection.json.jinja", **vars
        )
        placement.extend(r)

    c = render_ifc_template("ifc/placement/rel-placement-coords.json.jinja", **vars)
    placement.extend(c)
    return placement


def query_placement_rel_to(g: Graph, placement):
    parent = g.value(placement, IFC_CONCEPTS["placementrelto"])

    while parent is not None:
        new_parent = g.value(parent, IFC_CONCEPTS["placementrelto"])
        if new_parent is None:
            return parent
        else:
            parent = new_parent


def query_ifc_walls(g: Graph):
    wall_concepts = [
        "IFCWALLSTANDARDCASE",
        "IFCWALL",
        "IFCWALLELEMENTEDCASE",
    ]

    rep_query = """
    SELECT DISTINCT ?wall ?placement 
    WHERE {
        ?wall rdf:type ifc:IFCWALL  .
        ?wall ifc:objectplacement ?placement .
    }
    """

    qres = g.query(rep_query)
    logger.info("Total walls: %d", len(qres))
    wall_json = list()
    for r in qres:
        wall_id = get_entity_id(g, r["wall"], "wall")
        placement_id = get_entity_id(g, r["placement"], "placement")
        logger.debug("%s: %s", wall_id, placement_id)
        parent = query_placement_rel_to(g, r["placement"])
        logger.debug(
            "Highest level parent frame: %s", get_entity_id(g, parent, "placement")
        )

        w = render_ifc_template("ifc/walls/wall-entity.json.jinja", wall_id=wall_id)
        wall_json.append(w)

        # TODO this is hardcoded for now (list of length 1 for this type of wall)
        representation = query_product_shape_representations(g, r["wall"])[0]
        for s in g.objects(representation, IFC_CONCEPTS["items"]):
            depth, position, _, _, g_contents = transform_extruded_area_solid(
                g, wall_id, s
            )
            wall_json.extend(g_contents)

            w_rep = render_ifc_template(
                "ifc/walls/wall-representation.json.jinja",
                wall_id=wall_id,
                depth=depth,
            )
            wall_json.append(w_rep)

            # Wall placement
            # TODO for now it assumes position is not None
            # TODO this also implies that position is 0, 0?
            ap = transform_axis_placement_3d(g, position, wall_id)
            wall_json.extend(ap)
            op = render_ifc_template(
                "ifc/placement/object-placement.json.jinja",
                placement_id=wall_id,
            )
            wall_json.extend(op)
            rp = render_ifc_template(
                "ifc/placement/placement-rel-to.json.jinja",
                placement_id=wall_id,
                ref_placement_id=placement_id,
            )
            wall_json.extend(rp)

    return wall_json


def transform_extruded_area_solid(g: Graph, element_id, representation, parent_id=None):
    logger.debug("Transforming extruded area solid %s", element_id)
    graph_contents = list()
    if parent_id is None:
        parent_id = element_id
    depth, position, swept_area, ext_dir = query_extruded_area_solid(g, representation)

    swept_area_type = g.value(swept_area, RDF["type"])
    if swept_area_type == IFC_CONCEPTS["IFCARBITRARYCLOSEDPROFILEDEF"]:
        coords = query_arbitrary_closed_profile(g, swept_area)

        w_polygon = render_ifc_template(
            "ifc/walls/wall-polygon.json.jinja",
            parent_id=parent_id,
            element_id=element_id,
            coords=coords,
        )
        graph_contents.extend(w_polygon)
        w_polyhedron = render_ifc_template(
            "ifc/walls/wall-polyhedron.json.jinja",
            parent_id=parent_id,
            element_id=element_id,
            coords=coords,
            depth=depth,
            extruded_dir=ext_dir,
        )
        graph_contents.extend(w_polyhedron)
        add_polyhedron_faces(graph_contents)
        return depth, position, coords, ext_dir, graph_contents
    elif swept_area_type == IFC_CONCEPTS["IFCCIRCLEPROFILEDEF"]:
        center_pos = g.value(swept_area, IFC_CONCEPTS["position"])
        radius = g.value(swept_area, IFC_CONCEPTS["radius"])
        circle_id = get_entity_id(g, swept_area, "circle-profile")
        # center = transform_axis_placement_3d(g, position, parent_id)
        poly = render_ifc_template(
            "ifc/base/circle-profile.json.jinja",
            parent_id=parent_id,
            element_id=element_id,
            point_id=circle_id,
            radius=radius,
            depth=depth,
            extruded_dir=ext_dir,
            relative_placement=center_pos,
            rdflib=rdflib,
            list=list,
            IFC_CONCEPTS=IFC_CONCEPTS,
            g=g,
        )
        graph_contents.extend(poly)
        return depth, position, None, ext_dir, graph_contents
    elif swept_area_type == IFC_CONCEPTS["IFCRECTANGLEPROFILEDEF"]:
        xdim = g.value(swept_area, IFC_CONCEPTS["xdim"])
        ydim = g.value(swept_area, IFC_CONCEPTS["ydim"])
        x = xdim.toPython() / 2
        y = ydim.toPython() / 2
        z = depth.toPython() * ext_dir[-1].toPython()
        coords = [
            [-x, -y],
            [-x, y],
            [x, y],
            [x, -y],
            [-x, -y, z],
            [-x, y, z],
            [x, y, z],
            [x, -y, z],
        ]
        poly = render_ifc_template(
            "ifc/base/rectangle-profile.json.jinja",
            parent_id=parent_id,
            element_id=element_id,
            depth=depth,
            extruded_dir=ext_dir,
            coords=coords,
        )
        add_polyhedron_faces(poly)
        graph_contents.extend(poly)
        return depth, position, coords, ext_dir, graph_contents
    else:
        logger.warning("Support for {} not implemented yet".format(swept_area_type))


def query_extruded_area_solid(g: Graph, representation):
    logger.debug(representation)
    rep_query = """
    SELECT ?ext_dir ?depth ?swept_area ?position
    WHERE {
        ?representation ifc:depth ?depth .
        ?representation ifc:sweptarea ?swept_area .
        ?representation ifc:position ?position .
        ?representation ifc:extrudeddirection ?ext_dir .
    }
    """
    q = prepareQuery(rep_query, initNs={"ifc": IFC_CONCEPTS, "rdf": RDF})

    qres = g.query(q, initBindings={"representation": representation})
    assert len(qres) == 1
    res = list(qres)[0]
    ext_dir = get_list_values(g, res["ext_dir"], IFC_CONCEPTS["directionratios"])
    return res["depth"], res["position"], res["swept_area"], ext_dir


def query_arbitrary_closed_profile(g: Graph, profile):
    rep_query = """
    SELECT ?points
    WHERE {
        ?swept_area ifc:outercurve/ifc:points ?points .
    }
    """
    q = prepareQuery(rep_query, initNs={"ifc": IFC_CONCEPTS, "rdf": RDF})

    qres = g.query(q, initBindings={"swept_area": profile})
    assert len(qres) == 1
    res = list(qres)[0]

    coords = list()
    for ptr in get_list_values(g, res["points"], IFC_CONCEPTS["coordlist"]):
        c = get_list_from_ptr(g, ptr)
        c = [coord.toPython() for coord in c]
        coords.append(c)

    return coords


def query_product_shape_representations(g: Graph, product):
    # TODO it would be better to pass target_view, context identifier and type
    #  as arguments, but I couldn't find a way to pass them to the query
    rep_query = """
    SELECT ?representation
    WHERE {
        ?object ifc:representation/ifc:representations/rdf:rest*/rdf:first ?representation .
        ?representation ifc:contextofitems ?context .
        ?context ifc:targetview "MODEL_VIEW" .
        ?context ifc:contextidentifier "Body" .
        ?context ifc:contexttype "Model" .
    }
    """
    q = prepareQuery(rep_query, initNs={"ifc": IFC_CONCEPTS, "rdf": RDF})

    qres = g.query(q, initBindings={"object": product})
    representations = list()
    for row in qres:
        representations.append(row["representation"])

    return representations


def query_mapped_item(g: Graph, product):
    rep_query = """
    SELECT ?representation ?origin ?target
    WHERE {
        ?object ifc:mappingsource ?source .
        ?source ifc:mappingorigin ?origin .
        ?source ifc:mappedrepresentation ?representation .
        ?object ifc:mappingtarget ?target .
    }
    """

    q = prepareQuery(rep_query, initNs={"ifc": IFC_CONCEPTS, "rdf": RDF})

    qres = g.query(q, initBindings={"object": product})
    assert len(qres) == 1
    # for row in qres:
    res = list(qres)[0]
    return res["representation"], res["origin"], res["target"]


def transform_cartesian_transformation_operator(g: Graph, target, target_id):
    vars = dict(
        placement_id=target_id,
        g=g,
        target=target,
        IFC_CONCEPTS=IFC_CONCEPTS,
        rdflib=rdflib,
        list=list,
    )
    cto = render_ifc_template(
        "ifc/base/cartesian-transformation-operator.json.jinja", **vars
    )
    return cto


def query_ifc_doors(g: Graph):
    door_wall_query = """
    SELECT DISTINCT ?wall ?opening ?door ?voids ?fills
    WHERE {
        ?wall rdf:type ifc:IFCWALL  .
        ?opening rdf:type ifc:IFCOPENINGELEMENT  .
        ?door rdf:type ifc:IFCDOOR  .
        
        ?voids rdf:type ifc:IFCRELVOIDSELEMENT .
        ?voids ifc:relatingbuildingelement ?wall .
        ?voids ifc:relatedopeningelement ?opening .
        
        ?fills rdf:type ifc:IFCRELFILLSELEMENT .
        ?fills ifc:relatedbuildingelement ?door .
        ?fills ifc:relatingopeningelement ?opening .
    }
    """

    qres = g.query(door_wall_query)
    logger.info("Total Door-Wall relations: %d", len(qres))
    graph_contents = list()
    for r in qres:
        wall_id = get_entity_id(g, r["wall"], "wall")
        opening_id = get_entity_id(g, r["opening"], "opening")
        door_id = get_entity_id(g, r["door"], "door")
        logger.debug("%s <-- voids -- %s <-- fills -- %s", wall_id, opening_id, door_id)

        d = render_ifc_template(
            "ifc/doors/door-entity.json.jinja",
            door_id=door_id,
        )
        graph_contents.append(d)

        dl = render_ifc_template(
            "ifc/doors/door-lining.json.jinja",
            door_id=door_id,
        )
        graph_contents.append(dl)

        f = render_ifc_template(
            "ifc/doors/filling-rel.json.jinja",
            door_id=door_id,
            opening_id=opening_id,
        )

        o = render_ifc_template(
            "ifc/openings/entryway-entity.json.jinja",
            opening_id=opening_id,
        )
        graph_contents.append(o)

        v = render_ifc_template(
            "ifc/openings/voiding-rel.json.jinja",
            opening_id=opening_id,
            wall_id=wall_id,
        )
        graph_contents.append(v)

        logger.info("Processing doorway %s", opening_id)
        opening_reps = query_product_shape_representations(g, r["opening"])

        opening_placement = g.value(r["opening"], IFC_CONCEPTS["objectplacement"])
        opening_placement_id = get_entity_id(g, opening_placement, "placement")
        parent = query_placement_rel_to(g, opening_placement)

        # TODO The current test file only has a single door, test with a case with multiple mapped items

        for op_shape in g.objects(opening_reps, IFC_CONCEPTS["items"]):
            rep, origin, target = query_mapped_item(g, op_shape)
            origin_id = get_entity_id(g, origin, "mapping-origin")
            target_id = get_entity_id(g, target, "mapping-target")

            # Transformation of mapping origin (T) to mapping target (ref)
            axis_placement = transform_axis_placement_3d(g, origin, origin_id)
            graph_contents.extend(axis_placement)
            e = render_ifc_template(
                "ifc/placement/object-placement.json.jinja",
                placement_id=origin_id,
            )
            graph_contents.extend(e)
            pj = render_ifc_template(
                "ifc/placement/placement-rel-to.json.jinja",
                placement_id=origin_id,
                ref_placement_id=target_id,
            )
            graph_contents.extend(pj)

            # mapping target (T) to object placement (ref)
            cto = transform_cartesian_transformation_operator(g, target, target_id)
            graph_contents.extend(cto)
            e = render_ifc_template(
                "ifc/placement/object-placement.json.jinja",
                placement_id=target_id,
            )
            graph_contents.extend(e)
            pj = render_ifc_template(
                "ifc/placement/placement-rel-to.json.jinja",
                placement_id=target_id,
                ref_placement_id=opening_placement_id,
            )
            graph_contents.extend(pj)

            # Get the IfcRepresentationItems
            for o in g.objects(rep, IFC_CONCEPTS["items"]):
                solid_id = get_entity_id(g, o, "extruded-area-solid")
                # Individual points are specified wrt to extruded area solid frame/origin (ref)
                _, position, _, _, poly = transform_extruded_area_solid(
                    g, solid_id, o, parent_id=opening_id
                )
                graph_contents.extend(poly)

                # Transformation of extruded area solid (mapped repr, T) to mapping origin (ref)
                axis_placement = transform_axis_placement_3d(g, position, solid_id)
                graph_contents.extend(axis_placement)
                e = render_ifc_template(
                    "ifc/placement/object-placement.json.jinja",
                    placement_id=solid_id,
                )
                graph_contents.extend(e)
                pj = render_ifc_template(
                    "ifc/placement/placement-rel-to.json.jinja",
                    placement_id=solid_id,
                    ref_placement_id=origin_id,
                )
                graph_contents.extend(pj)

        logger.info("Processing door %s", door_id)
        door_reps = query_product_shape_representations(g, r["door"])
        door_placement = g.value(r["door"], IFC_CONCEPTS["objectplacement"])
        door_placement_id = get_entity_id(g, door_placement, "placement")
        parent = query_placement_rel_to(g, door_placement)

        for d_shape, suffix in zip(
            g.objects(door_reps, IFC_CONCEPTS["items"]), ["", "-lining"]
        ):
            rep, origin, target = query_mapped_item(g, d_shape)
            origin_id = get_entity_id(g, origin, "mapping-origin")
            target_id = get_entity_id(g, target, "mapping-target")

            # Transformation of mapping origin (T) to mapping target (ref)
            axis_placement = transform_axis_placement_3d(g, origin, origin_id)
            graph_contents.extend(axis_placement)
            e = render_ifc_template(
                "ifc/placement/object-placement.json.jinja",
                placement_id=origin_id,
            )
            graph_contents.extend(e)
            pj = render_ifc_template(
                "ifc/placement/placement-rel-to.json.jinja",
                placement_id=origin_id,
                ref_placement_id=target_id,
            )
            graph_contents.extend(pj)

            # mapping target (T) to object placement (ref)
            cto = transform_cartesian_transformation_operator(g, target, target_id)
            graph_contents.extend(cto)
            e = render_ifc_template(
                "ifc/placement/object-placement.json.jinja",
                placement_id=target_id,
            )
            graph_contents.extend(e)
            pj = render_ifc_template(
                "ifc/placement/placement-rel-to.json.jinja",
                placement_id=target_id,
                ref_placement_id=door_placement_id,
            )
            graph_contents.extend(pj)
            for d in g.objects(rep, IFC_CONCEPTS["items"]):
                parent_id = door_id + suffix
                shape = transform_polygonal_face_set(
                    g, d, parent_id=parent_id, placement_id=origin_id
                )
                graph_contents.extend(shape)

    return graph_contents


def transform_polygonal_face_set(g, element, parent_id, placement_id=None):
    solid_id = get_entity_id(g, element, "polygonal-face-set")
    if placement_id is None:
        placement_id = solid_id
    logger.debug("Transforming %s", solid_id)
    # TODO the frame version doesn't seem to include a polygon concept...
    #  Not including it for now, but review if it's needed
    coord_list = rdflib.collection.Collection(
        g,
        g[element : IFC_CONCEPTS["coordinates"] / IFC_CONCEPTS["coordlist"]].__next__(),
    )
    faces = rdflib.collection.Collection(
        g,
        g[element : IFC_CONCEPTS["faces"]].__next__(),
    )
    poly = render_ifc_template(
        "ifc/base/polygonal-face-set.json.jinja",
        element_id=solid_id,
        # TODO Add a separate frame for the object? Is it needed?
        #  The IFCPOLYGONALFACESET concept doesn't have an origin.
        #  If adding a frame, it would be hardcoded to no translation and no rotation
        placement_id=placement_id,  # Transformation of the individual points to mapping origin (ref)
        parent_id=parent_id,
        coords=coord_list,
        faces=faces,
        g=g,
        rdflib=rdflib,
        list=list,
        IFC_CONCEPTS=IFC_CONCEPTS,
    )
    return poly


def query_ifc_spaces(g: Graph, model_name):
    graph_contents = []
    spaces = []
    for s in g.subjects(RDF.type, IFC_CONCEPTS["IFCSPACE"]):
        space_id = get_entity_id(g, s, "space")
        spaces.append(space_id)

        space_placement = g.value(s, IFC_CONCEPTS["objectplacement"])
        space_placement_id = get_entity_id(g, space_placement, "placement")
        logger.info("Processing %s", space_id)
        parent = query_placement_rel_to(g, space_placement)
        space_json = render_ifc_template(
            "ifc/spaces/space-entity.json.jinja",
            space_id=space_id,
            space_ref_frame=space_placement_id,
            model_name=model_name,
        )
        graph_contents.extend(space_json)

        space_reps = query_product_shape_representations(g, s)
        for space_shape in g.objects(space_reps, IFC_CONCEPTS["items"]):
            solid_id = get_entity_id(g, space_shape, "polygonal-face-set")
            # TODO Check if the space frame is needed.
            #  The points could be defined wrt to the space_placement_id directly
            poly = transform_polygonal_face_set(
                g, space_shape, space_id, placement_id=space_id
            )
            graph_contents.extend(poly)
            # TODO We create a polygon of the space by identifying the face that has an equal and the minimum z value
            #  This has assumptions about frames and coords that may not generalize.
            #  This is currently needed for the scenery_builder queries
            points = get_space_polygon_points(g, space_shape)
            polygon = render_ifc_template(
                "ifc/spaces/space-polygon.json.jinja",
                parent_id=space_id,
                element_id=solid_id,
                points=points,
            )
            graph_contents.extend(polygon)

    # TODO This is needed because "spaces" in the metamodel has a @list container. It should probably be a set instead
    graph_contents.append({"@id": model_name, "spaces": spaces})
    return graph_contents


def get_space_polygon_points(g: Graph, space_shape):
    import numpy as np

    all_points = []
    coord_list = rdflib.collection.Collection(
        g,
        g[
            space_shape : IFC_CONCEPTS["coordinates"] / IFC_CONCEPTS["coordlist"]
        ].__next__(),
    )
    for p in coord_list:
        coords = [c.toPython() for c in rdflib.collection.Collection(g, p)]
        all_points.append(coords)

    all_points = np.array(all_points)
    min_height = np.min(all_points[:, 2])

    faces = rdflib.collection.Collection(
        g,
        g[space_shape : IFC_CONCEPTS["faces"]].__next__(),
    )
    for f in faces:
        coord_idx = rdflib.collection.Collection(
            g, g[f : IFC_CONCEPTS["coordindex"]].__next__()
        )
        face_height = {all_points[idx.toPython() - 1][-1] for idx in coord_idx}
        if len(face_height) == 1 and list(face_height)[0] == min_height:
            return coord_idx


def query_ifc_units(g: Graph):
    print("\nUnits...\n-----------------")
    units_query = """
    SELECT ?unit ?name ?unittype ?prefix ?dimensions
    WHERE {
        ?unit rdf:type ifc:IFCSIUNIT  .
        ?unit qudt:hasUnit ?name .
        ?unit qudt:hasQuantityKind ?unittype .
        OPTIONAL { ?unit ifc:prefix ?prefix}
        OPTIONAL{ ?unit ifc:dimensions ?dimensions}
    }
    """

    print("@id\tname\tunittype\tprefix\tdimensions")
    qres = g.query(units_query)
    for row in qres:
        print(
            "{}\t{}\t{}\t{}\t{}".format(
                get_entity_id(g, row["unit"], "unit"),
                row["name"],
                row["unittype"],
                row["prefix"],
                row["dimensions"],
            )
        )
    convert_units_query = """
    SELECT ?unit ?name ?unittype ?prefix ?dimensions ?factor
    WHERE {
        ?unit rdf:type ifc:IFCCONVERSIONBASEDUNIT  .
        ?unit ifc:name ?name .
        ?unit ifc:unittype ?unittype .
        OPTIONAL { ?unit ifc:prefix ?prefix}
        OPTIONAL{ ?unit ifc:dimensions ?dimensions}
        OPTIONAL{ ?unit ifc:conversionfactor ?factor}
    }
    """

    qres = g.query(convert_units_query)
    print("\n@id\tname\tunittype\tprefix\tdimensions\tconv. factor")
    for row in qres:
        print(
            "{}\t{}\t{}\t{}\t{}\t{}".format(
                get_entity_id(g, row["unit"], "unit"),
                row["name"],
                row["unittype"],
                row["prefix"],
                row["dimensions"],
                row["factor"],
            )
        )


def query_ifc_task_elements(g, elements=["IFCOUTLET", "IFCDUCTSEGMENT"]):
    logger.info("Querying for: {}".format(elements))
    task_query = """
    SELECT DISTINCT ?wall ?opening ?object ?voids ?fills
    WHERE {
        ?wall rdf:type ifc:IFCWALL  .
        ?opening rdf:type ifc:IFCOPENINGELEMENT  .
        ?object rdf:type ?object_type  .
        
        ?voids rdf:type ifc:IFCRELVOIDSELEMENT .
        ?voids ifc:relatingbuildingelement ?wall .
        ?voids ifc:relatedopeningelement ?opening .
        
        ?fills rdf:type ifc:IFCRELFILLSELEMENT .
        ?fills ifc:relatedbuildingelement ?object .
        ?fills ifc:relatingopeningelement ?opening .
    }
    """
    q = prepareQuery(task_query, initNs={"ifc": IFC_CONCEPTS, "rdf": RDF})

    graph_contents = list()

    for concept in elements:
        logger.info("Processing {}s".format(concept))
        qres = g.query(q, initBindings={"object_type": IFC_CONCEPTS[concept]})
        logger.info("Total elements: %d", len(qres))
        for row in qres:
            wall_id = get_entity_id(g, row["wall"], "wall")
            opening_id = get_entity_id(g, row["opening"], "opening")
            object_id = get_entity_id(
                g, row["object"], concept.replace("IFC", "").lower()
            )
            logger.info("Processing {}".format(object_id))
            logger.debug(
                "%s <-- voids -- %s <-- fills -- %s", wall_id, opening_id, object_id
            )
            o = render_ifc_template(
                "ifc/openings/opening-entity.json.jinja",
                opening_id=opening_id,
            )
            graph_contents.append(o)

            opening_placement = g.value(row["opening"], IFC_CONCEPTS["objectplacement"])
            opening_placement_id = get_entity_id(g, opening_placement, "placement")

            opening_reps = query_product_shape_representations(g, row["opening"])
            for rep in g.objects(opening_reps, IFC_CONCEPTS["items"]):
                logger.debug("Shape representation: %s", g.value(rep, RDF["type"]))
                if g.value(rep, RDF["type"]) != IFC_CONCEPTS["IFCEXTRUDEDAREASOLID"]:
                    logger.warning("Not an extruded area solid representation")
                    continue
                solid_id = get_entity_id(g, rep, "extruded-area-solid")
                # Individual points are specified wrt to extruded area solid frame/origin (ref)
                _, position, _, _, poly = transform_extruded_area_solid(
                    g, solid_id, rep, parent_id=opening_id
                )
                graph_contents.extend(poly)

                # Transformation of extruded area solid (mapped repr, T) to mapping origin (ref)
                axis_placement = transform_axis_placement_3d(g, position, solid_id)
                graph_contents.extend(axis_placement)
                e = render_ifc_template(
                    "ifc/placement/object-placement.json.jinja",
                    placement_id=solid_id,
                )
                graph_contents.extend(e)
                pj = render_ifc_template(
                    "ifc/placement/placement-rel-to.json.jinja",
                    placement_id=solid_id,
                    ref_placement_id=opening_placement_id,
                )
                graph_contents.extend(pj)

            for x in ["wall", "opening", "object"]:
                placement = g.value(row[x], IFC_CONCEPTS["objectplacement"])
                parent = query_placement_rel_to(g, placement)
                print("\t", get_entity_id(g, parent, "placement"))

    return graph_contents


def stats(g):
    voiding_query = """
    SELECT DISTINCT ?wall ?opening 
    WHERE {
        ?wall rdf:type ifc:IFCWALL  .
        ?opening rdf:type ifc:IFCOPENINGELEMENT  .
        ?r rdf:type ifc:IFCRELVOIDSELEMENT .
        ?r ifc:relatingbuildingelement ?wall .
        ?r ifc:relatedopeningelement ?opening .
    }
    """

    print()
    qres = g.query(voiding_query)
    print("Total openings voiding walls:", len(qres))
    # for r in qres:
    #     print(
    #         get_entity_id(g, r["opening"], "opening"),
    #         " --> voids --> ",
    #         get_entity_id(g, r["wall"], "wall"),
    #     )
    #
    filling_query = """
    SELECT DISTINCT ?object ?opening 
    WHERE {
        ?opening rdf:type ifc:IFCOPENINGELEMENT  .
        ?r rdf:type ifc:IFCRELFILLSELEMENT .
        ?r ifc:relatedbuildingelement ?object .
        ?r ifc:relatingopeningelement ?opening .
    }
    """
    qres = g.query(filling_query)
    print("Total objects filling openings:", len(qres))
    # for r in qres:
    #     print(
    #         get_entity_id(g, r["object"], "object"),
    #         " --> fills --> ",
    #         get_entity_id(g, r["opening"], "opening"),
    #     )
