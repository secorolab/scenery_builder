import json
import os
import logging

import rdflib
from rdflib import Graph, RDF, URIRef
from rdflib.plugins.sparql import prepareQuery

from fpm.graph import get_list_values, get_list_from_ptr
from fpm.utils import load_template, save_file
from ifcld.interpreters.namespaces import IFC_CONCEPTS
from ifcld.query import (
    units_query,
    convert_units_query,
    project_units_query,
    spatial_decomposition,
    top_sites,
    building_storeys,
    spatial_containment,
    cartesian_point,
)

logger = logging.getLogger("floorplan.generators.scenery")
logger.setLevel(logging.DEBUG)

WALL_CONCEPTS = [
    IFC_CONCEPTS["IFCWALLSTANDARDCASE"],
    IFC_CONCEPTS["IFCWALL"],
    IFC_CONCEPTS["IFCWALLELEMENTEDCASE"],
]


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
        "https://secorolab.github.io/metamodels/ifc/",
    )

    # Get the FPM context template for this model
    fp_ctx_template = load_template("ifc/fpm-context.json.jinja")
    fpm_ctx = json.loads(fp_ctx_template.render(model_id=model_name))

    length_unit = str(g.namespace_manager.curie(query_ifc_units(g)[0])).split(":")[-1]

    sp_dec = prepareQuery(
        spatial_decomposition, initNs={"ifc": IFC_CONCEPTS, "rdf": RDF}
    )
    sp_cont = prepareQuery(
        spatial_containment, initNs={"ifc": IFC_CONCEPTS, "rdf": RDF}
    )
    # project = g.value(predicate=RDF.type, object=IFC_CONCEPTS["IFCPROJECT"])
    qres = g.query(building_storeys)
    for storey, name in qres:
        logger.info("Storey: %s. URI: %s", name, storey)
        children_result = g.query(sp_dec, initBindings={"parent": storey})
        children = list(children_result)
        containment_results = g.query(sp_cont, initBindings={"element": storey})
        contains = list(containment_results)

        cont_spaces = list()
        while children:
            child, concept_type = children.pop()
            if concept_type == IFC_CONCEPTS["IFCSPACE"]:
                cont_spaces.append((child, concept_type))
            else:
                logger.error("Child concept: %s of type %s", child, concept_type)
            children_result = g.query(sp_dec, initBindings={"parent": child})
            children.extend(list(children_result))
            containment_results = g.query(sp_cont, initBindings={"element": child})
            contains.extend(list(containment_results))

        storey_output_path = os.path.join(
            output_path, str(name).lower().replace(" ", "-")
        )

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
            storey_output_path,
            "{}.floorplan.fpm.json".format(model_name),
            {"@graph": floorplan, "@context": fpm_ctx},
        )

        logger.info("Transforming IFC local placements...")
        placements = query_ifc_local_placements(g, length_unit)
        save_file(
            storey_output_path,
            "{}.placement.fpm.json".format(model_name),
            {"@graph": placements, "@context": fpm_ctx},
        )

        logger.info("Transforming IFC walls...")
        walls = query_ifc_walls(g, contains, length_unit)
        save_file(
            storey_output_path,
            "{}.walls.fpm.json".format(model_name),
            {"@graph": walls, "@context": fpm_ctx},
        )

        logger.info("Transforming IFC doors...")
        doors = query_ifc_doors(g, contains, length_unit)
        save_file(
            storey_output_path,
            "{}.doors.fpm.json".format(model_name),
            {"@graph": doors, "@context": fpm_ctx},
        )

        logger.info("Transforming IFC spaces...")
        spaces = query_ifc_spaces(g, cont_spaces, model_name, length_unit)
        save_file(
            storey_output_path,
            "{}.spaces.fpm.json".format(model_name),
            {"@graph": spaces, "@context": fpm_ctx},
        )

        logger.info("Transforming task elements...")
        task_elements = query_ifc_task_elements(g, contains, length_unit)
        save_file(
            storey_output_path,
            "{}.task.fpm.json".format(model_name),
            {"@graph": task_elements, "@context": fpm_ctx},
        )

    stats(g)
    # query_spatial_decomposition(g)

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


def query_spatial_decomposition(g: Graph):
    composition_types = ["COMPLEX", "ELEMENT", "PARTIAL"]
    elements = ["IFCSITE", "IFCBUILDING", "IFCBUILDINGSTOREY", "IFCSPACE"]
    qres = g.query(spatial_decomposition)
    for r in list(qres):
        # print(r.asdict())
        print(
            r["parent_name"],
            r["comp_type"],
            r["child_name"],
            r["contains"],
            r["contains_type"],
        )


def query_ifc_local_placements(g: Graph, length_unit):
    placements = list()
    world_frame = list()

    for p in g.subjects(RDF.type, IFC_CONCEPTS["IFCLOCALPLACEMENT"]):
        entity = get_entity_id(g, p)
        e = render_ifc_template(
            "ifc/placement/object-placement.json.jinja",
            placement_id=entity,
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
        ap = transform_axis_placement_3d(g, rp, entity, length_unit)
        placements.extend(ap)

    return placements


def transform_axis_placement_3d(g: Graph, rel_placement, entity, length_unit):
    placement = list()
    vars = dict(
        placement_id=entity,
        g=g,
        relative_placement=rel_placement,
        IFC_CONCEPTS=IFC_CONCEPTS,
        rdflib=rdflib,
        list=list,
        length_unit=length_unit,
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


def query_ifc_walls(g: Graph, walls, length_unit):

    rep_query = """
    SELECT DISTINCT ?wall ?placement 
    WHERE {
        ?wall rdf:type ifc:IFCWALL  .
        ?wall ifc:objectplacement ?placement .
    }
    """

    qres = g.query(rep_query)
    # logger.info("Total walls: %d", len(qres))
    wall_json = list()
    for wall, wall_type in walls:
        if wall_type not in WALL_CONCEPTS:
            continue
        placement = g.value(wall, IFC_CONCEPTS["objectplacement"])
        # wall_id = get_entity_id(g, r["wall"], "wall")
        # placement_id = get_entity_id(g, r["placement"], "placement")
        wall_id = get_entity_id(g, wall, "wall")
        placement_id = get_entity_id(g, placement, "placement")
        logger.debug("%s: %s", wall_id, placement_id)
        # parent = query_placement_rel_to(g, r["placement"])
        # logger.debug(
        #     "Highest level parent frame: %s", get_entity_id(g, parent, "placement")
        # )

        w = render_ifc_template("ifc/walls/wall-entity.json.jinja", wall_id=wall_id)
        wall_json.append(w)

        # TODO this is hardcoded for now (list of length 1 for this type of wall)
        representation = query_product_shape_representations(g, wall)[0]
        for s in g.objects(representation, IFC_CONCEPTS["items"]):
            if g.value(s, RDF["type"]) == IFC_CONCEPTS["IFCEXTRUDEDAREASOLID"]:

                depth, position, _, _, g_contents = transform_extruded_area_solid(
                    g, wall_id, s, length_unit
                )
                wall_json.extend(g_contents)

                w_rep = render_ifc_template(
                    "ifc/walls/wall-representation.json.jinja",
                    wall_id=wall_id,
                    depth=depth,
                    length_unit=length_unit,
                )
                wall_json.append(w_rep)

                # Wall placement
                # TODO for now it assumes position is not None
                # TODO this also implies that position is 0, 0?
                ap = transform_axis_placement_3d(g, position, wall_id, length_unit)
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
            elif g.value(s, RDF.type) == IFC_CONCEPTS["IFCMAPPEDITEM"]:
                rep, origin, target = query_mapped_item(g, s)
                origin_id = wall_id + "-" + get_entity_id(g, origin, "mapping-origin")
                target_id = get_entity_id(g, target, "mapping-target")

                wall_json.extend(
                    transform_mapped_item(
                        g, origin, origin_id, target, placement_id, length_unit
                    )
                )

                # Get the IfcRepresentationItems
                for o in g.objects(rep, IFC_CONCEPTS["items"]):
                    if g.value(o, RDF["type"]) == IFC_CONCEPTS["IFCEXTRUDEDAREASOLID"]:
                        shape = transform_mapped_extruded_area_solid(
                            g, o, wall_id, origin_id, length_unit
                        )
                    elif g.value(o, RDF["type"]) == IFC_CONCEPTS["IFCFACETEDBREP"]:
                        shape = transform_faceted_brep(
                            g, o, wall_id, length_unit, placement_id
                        )
                    else:
                        raise ValueError(
                            "Unsupported item: %s", g.value(o, RDF["type"])
                        )

                    wall_json.extend(shape)

            elif g.value(s, RDF["type"]) == IFC_CONCEPTS["IFCPOLYGONALFACESET"]:

                shape = transform_polygonal_face_set(
                    g, s, wall_id, length_unit, placement_id=placement_id
                )

                wall_json.extend(shape)
            elif g.value(s, RDF["type"]) == IFC_CONCEPTS["IFCFACETEDBREP"]:
                shape = transform_faceted_brep(
                    g, s, wall_id, length_unit, placement_id=placement_id
                )
                wall_json.extend(shape)
            elif g.value(s, RDF["type"]) == IFC_CONCEPTS["IFCBOOLEANCLIPPINGRESULT"]:
                transform_unsupported_shapes(g, s)
            else:
                raise ValueError("Unsupported type %s" % g.value(s, RDF["type"]))

    return wall_json


def transform_unsupported_shapes(g: Graph, element):
    logger.error("Unsupported item type: %s", g.value(element, RDF["type"]))


def transform_faceted_brep(
    g: Graph, element, parent_id=None, length_unit=None, placement_id=None
):
    solid_id = get_entity_id(g, element, "faceted-brep")
    logger.debug("Transforming %s", solid_id)

    faces = list()
    points = set()

    for face in g[element : IFC_CONCEPTS["outer"] / IFC_CONCEPTS["cfsfaces"]]:
        bounds = g[face : IFC_CONCEPTS["bounds"]]
        out_bounds = [
            b
            for b in bounds
            if g.value(b, RDF["type"]) == IFC_CONCEPTS["IFCFACEOUTERBOUND"]
        ]
        assert len(out_bounds) == 1
        bound = list(g[out_bounds[0] : IFC_CONCEPTS["bound"]])
        assert len(bound) == 1
        bound = bound.pop()

        if g.value(bound, RDF["type"]) == IFC_CONCEPTS["IFCPOLYLOOP"]:
            face_points = list()
            poly_points = rdflib.collection.Collection(
                g, g.value(bound, IFC_CONCEPTS["polygon"])
            )
            for point in poly_points:
                p = g.query(cartesian_point, initBindings={"point": point})
                coords = tuple([a.toPython() for (a,) in p])
                points.add(coords)
                face_points.append(coords)
            faces.append(face_points)
        else:
            logger.error("Unsupported item type: %s", g.value(bound, RDF["type"]))

    points = list(points)
    faces_idx = list()
    for f in faces:
        faces_idx.append([points.index(p) for p in f])

    poly = render_ifc_template(
        "ifc/base/faceted-brep.json.jinja",
        element_id=solid_id,
        parent_id=parent_id,
        placement_id=placement_id,
        points=points,
        faces=faces_idx,
        g=g,
        rdflib=rdflib,
        list=list,
        IFC_CONCEPTS=IFC_CONCEPTS,
        length_unit=length_unit,
    )

    return poly


def transform_extruded_area_solid(
    g: Graph, element_id, representation, length_unit, parent_id=None
):
    logger.debug("Transforming extruded area solid %s", element_id)
    graph_contents = list()
    if parent_id is None:
        parent_id = element_id

    depth, position, swept_area, ext_dir = query_extruded_area_solid(g, representation)

    swept_area_type = g.value(swept_area, RDF["type"])
    if swept_area_type == IFC_CONCEPTS["IFCARBITRARYCLOSEDPROFILEDEF"]:
        logger.debug("Swept area: %s has arbitrary closed profile", swept_area)
        coords = query_arbitrary_closed_profile(g, swept_area)

        w_polygon = render_ifc_template(
            "ifc/walls/wall-polygon.json.jinja",
            parent_id=parent_id,
            element_id=element_id,
            coords=coords,
            length_unit=length_unit,
        )
        graph_contents.extend(w_polygon)
        w_polyhedron = render_ifc_template(
            "ifc/walls/wall-polyhedron.json.jinja",
            parent_id=parent_id,
            element_id=element_id,
            coords=coords,
            depth=depth,
            extruded_dir=ext_dir,
            length_unit=length_unit,
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
            length_unit=length_unit,
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
            length_unit=length_unit,
        )
        add_polyhedron_faces(poly)
        graph_contents.extend(poly)
        return depth, position, coords, ext_dir, graph_contents
    else:
        logger.warning("Support for {} not implemented yet".format(swept_area_type))


def query_extruded_area_solid(g: Graph, representation):
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

    logger.debug("Querying extruded area solid for {}".format(representation))

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
    oc_type = g.value(profile, IFC_CONCEPTS["outercurve"] / RDF.type)
    if oc_type == IFC_CONCEPTS["IFCINDEXEDPOLYCURVE"]:
        qres = g.query(q, initBindings={"swept_area": profile})
        assert len(qres) == 1
        res = list(qres)[0]

        coords = list()
        for ptr in get_list_values(g, res["points"], IFC_CONCEPTS["coordlist"]):
            c = get_list_from_ptr(g, ptr)
            c = [coord.toPython() for coord in c]
            coords.append(c)

        return coords
    elif oc_type == IFC_CONCEPTS["IFCPOLYLINE"]:
        qres = g.query(q, initBindings={"swept_area": profile})
        coords = list()
        for (p,) in qres:
            c = get_list_values(g, p, IFC_CONCEPTS["coordinates"])
            c = [coord.toPython() for coord in c]
            coords.append(c)

        return coords
    else:
        raise ValueError("Outer curve type {} not supported".format(oc_type))


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

    print(representations)
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


def transform_cartesian_transformation_operator(
    g: Graph, target, target_id, length_unit
):
    vars = dict(
        placement_id=target_id,
        g=g,
        target=target,
        IFC_CONCEPTS=IFC_CONCEPTS,
        rdflib=rdflib,
        list=list,
        length_unit=length_unit,
    )
    logger.debug("Mapping target: %s", target)
    cto = render_ifc_template(
        "ifc/base/cartesian-transformation-operator.json.jinja", **vars
    )
    return cto


def transform_mapped_item(
    g: Graph, origin, origin_id, target, object_placement_id, length_unit
):
    graph_contents = list()

    target_id = get_entity_id(g, target, "mapping-target")

    # Transformation of mapping origin (T) to mapping target (ref)
    axis_placement = transform_axis_placement_3d(g, origin, origin_id, length_unit)
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
    cto = transform_cartesian_transformation_operator(g, target, target_id, length_unit)
    graph_contents.extend(cto)
    e = render_ifc_template(
        "ifc/placement/object-placement.json.jinja",
        placement_id=target_id,
    )
    graph_contents.extend(e)
    pj = render_ifc_template(
        "ifc/placement/placement-rel-to.json.jinja",
        placement_id=target_id,
        ref_placement_id=object_placement_id,
    )
    graph_contents.extend(pj)

    return graph_contents


def transform_mapped_extruded_area_solid(
    g: Graph, rep, parent_id, origin_id, length_unit
):
    graph_contents = list()
    solid_id = parent_id + "-" + get_entity_id(g, rep, "extruded-area-solid")
    # Individual points are specified wrt to extruded area solid frame/origin (ref)
    _, position, _, _, poly = transform_extruded_area_solid(
        g, solid_id, rep, length_unit, parent_id=parent_id
    )
    graph_contents.extend(poly)

    # Transformation of extruded area solid (mapped repr, T) to mapping origin (ref)
    axis_placement = transform_axis_placement_3d(g, position, solid_id, length_unit)
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

    return graph_contents


def query_ifc_doors(g: Graph, doors, length_unit):
    door_wall_query = """
    SELECT DISTINCT ?wall ?opening ?wall_type
    WHERE {
        ?wall rdf:type ?wall_type .
        ?opening rdf:type ifc:IFCOPENINGELEMENT  .
        
        ?voids ifc:relatingbuildingelement ?wall .
        ?voids ifc:relatedopeningelement ?opening .
        
        ?fills ifc:relatedbuildingelement ?door .
        ?fills ifc:relatingopeningelement ?opening .
    }
    """
    # ?voids rdf:type ifc:IFCRELVOIDSELEMENT .
    # ?fills rdf:type ifc:IFCRELFILLSELEMENT .

    q = prepareQuery(door_wall_query, initNs={"ifc": IFC_CONCEPTS, "rdf": RDF})

    graph_contents = list()
    for door, door_type in doors:
        if door_type not in [IFC_CONCEPTS["IFCDOOR"]]:
            continue
        door_id = get_entity_id(g, door, "door")
        logger.info("Querying for door {}".format(door_id))

        qres = g.query(q, initBindings={"door": door})
        assert len(list(qres)) == 1
        wall, opening, wall_type = list(qres)[0]
        try:
            assert wall_type in WALL_CONCEPTS
        except AssertionError:
            logger.error("Wall type {} not in Wall Concepts".format(wall_type))
            continue
        wall_id = get_entity_id(g, wall, "wall")
        opening_id = get_entity_id(g, opening, "opening")
        logger.debug("%s <-- voids -- %s <-- fills -- %s", wall_id, opening_id, door_id)

        d = render_ifc_template(
            "ifc/doors/door-entity.json.jinja",
            door_id=door_id,
        )
        graph_contents.append(d)

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
        opening_reps = query_product_shape_representations(g, opening)

        opening_placement = g.value(opening, IFC_CONCEPTS["objectplacement"])
        opening_placement_id = get_entity_id(g, opening_placement, "placement")
        parent = query_placement_rel_to(g, opening_placement)

        for op_shape in g.objects(opening_reps, IFC_CONCEPTS["items"]):
            if g.value(op_shape, RDF["type"]) == IFC_CONCEPTS["IFCMAPPEDITEM"]:
                rep, origin, target = query_mapped_item(g, op_shape)
                origin_id = (
                    opening_id + "-" + get_entity_id(g, origin, "mapping-origin")
                )
                target_id = get_entity_id(g, target, "mapping-target")

                graph_contents.extend(
                    transform_mapped_item(
                        g, origin, origin_id, target, opening_placement_id, length_unit
                    )
                )

                # Get the IfcRepresentationItems
                for o in g.objects(rep, IFC_CONCEPTS["items"]):
                    graph_contents.extend(
                        transform_mapped_extruded_area_solid(
                            g, o, opening_id, origin_id, length_unit
                        )
                    )
            elif g.value(op_shape, RDF["type"]) == IFC_CONCEPTS["IFCEXTRUDEDAREASOLID"]:
                depth, position, _, _, g_contents = transform_extruded_area_solid(
                    g, opening_id, op_shape, length_unit
                )
                graph_contents.extend(g_contents)

                w_rep = render_ifc_template(
                    "ifc/walls/wall-representation.json.jinja",
                    wall_id=opening_id,
                    depth=depth,
                    length_unit=length_unit,
                )
                graph_contents.append(w_rep)

                ap = transform_axis_placement_3d(g, position, opening_id, length_unit)
                graph_contents.extend(ap)
                op = render_ifc_template(
                    "ifc/placement/object-placement.json.jinja",
                    placement_id=opening_id,
                )
                graph_contents.extend(op)
                rp = render_ifc_template(
                    "ifc/placement/placement-rel-to.json.jinja",
                    placement_id=opening_id,
                    ref_placement_id=opening_placement_id,
                )
                graph_contents.extend(rp)
            else:
                raise ValueError(
                    "Unsupported shape: {}".format(g.value(op_shape, RDF["type"]))
                )

        logger.info("Processing door %s", door_id)
        door_reps = query_product_shape_representations(g, door)
        door_placement = g.value(door, IFC_CONCEPTS["objectplacement"])
        door_placement_id = get_entity_id(g, door_placement, "placement")
        parent = query_placement_rel_to(g, door_placement)

        for d_shape in g.objects(door_reps, IFC_CONCEPTS["items"]):
            if g.value(d_shape, RDF["type"]) == IFC_CONCEPTS["IFCMAPPEDITEM"]:
                rep, origin, target = query_mapped_item(g, d_shape)
                origin_id = door_id + "-" + get_entity_id(g, origin, "mapping-origin")
                target_id = get_entity_id(g, target, "mapping-target")

                graph_contents.extend(
                    transform_mapped_item(
                        g, origin, origin_id, target, door_placement_id, length_unit
                    )
                )

                handle = 1
                lining = 1
                panel = 1
                logger.debug(
                    "Total representation items: %s",
                    len(list(g.objects(rep, IFC_CONCEPTS["items"]))),
                )
                for i in g.objects(rep, IFC_CONCEPTS["items"]):
                    shape_aspect = get_shape_aspect(g, i)
                    if shape_aspect is not None:
                        shape_aspect = str(shape_aspect).lower()
                    else:
                        logger.warning("No shape aspect for item: %s", i)
                        shape_aspect = "panel"

                    if shape_aspect == "lining":
                        parent_id = f"{door_id}-{shape_aspect}-{lining}"
                        dl = render_ifc_template(
                            "ifc/doors/door-lining.json.jinja",
                            element_id=parent_id,
                            door_id=door_id,
                        )
                        graph_contents.extend(dl)
                        lining = lining + 1
                    elif shape_aspect == "handle":
                        parent_id = f"{door_id}-{shape_aspect}-{handle}"
                        dh = render_ifc_template(
                            "ifc/doors/door-handle.json.jinja",
                            door_id=door_id,
                            element_id=parent_id,
                        )
                        graph_contents.extend(dh)
                        handle = handle + 1
                    elif shape_aspect == "panel":
                        parent_id = f"{door_id}-{shape_aspect}-{panel}"
                        dp = render_ifc_template(
                            "ifc/doors/door-panel.json.jinja",
                            door_id=door_id,
                            element_id=parent_id,
                        )
                        graph_contents.extend(dp)
                        panel = panel + 1
                    else:
                        raise ValueError("Unknown shape aspect: %s" % shape_aspect)

                    if g.value(i, RDF["type"]) == IFC_CONCEPTS["IFCPOLYGONALFACESET"]:
                        shape = transform_polygonal_face_set(
                            g, i, parent_id, length_unit, placement_id=origin_id
                        )
                        graph_contents.extend(shape)
                    elif (
                        g.value(i, RDF["type"]) == IFC_CONCEPTS["IFCEXTRUDEDAREASOLID"]
                    ):
                        shape = transform_mapped_extruded_area_solid(
                            g, i, parent_id, origin_id, length_unit
                        )
                        graph_contents.extend(shape)
                    elif g.value(i, RDF["type"]) == IFC_CONCEPTS["IFCFACETEDBREP"]:
                        shape = transform_faceted_brep(
                            g, i, parent_id, length_unit, origin_id
                        )
                        graph_contents.extend(shape)
                    else:
                        transform_unsupported_shapes(g, i)

            elif g.value(d_shape, RDF["type"]) == IFC_CONCEPTS["IFCFACETEDBREP"]:
                _poly = transform_faceted_brep(
                    g, d_shape, door_id, length_unit, door_placement_id
                )
                graph_contents.extend(_poly)
            else:
                raise ValueError(
                    "Unsupported shape: {}".format(g.value(d_shape, RDF["type"]))
                )
    return graph_contents


def get_shape_aspect(g: Graph, rep):
    query = """
    SELECT DISTINCT ?shape_rep ?shape_aspect ?shape_aspect_name
    WHERE {
        ?shape_aspect rdf:type ifc:IFCSHAPEASPECT  .
        ?shape_aspect ifc:shaperepresentations/rdf:rest*/rdf:first ?shape_rep .
        ?shape_rep ifc:items ?item .
        ?shape_aspect ifc:name ?shape_aspect_name .
    }
    """
    qres = g.query(query, initBindings={"item": rep})
    if len(list(qres)) == 0:
        return None
    assert len(qres) == 1

    return list(qres)[0]["shape_aspect_name"]


def transform_polygonal_face_set(g, element, parent_id, length_unit, placement_id=None):
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
        length_unit=length_unit,
    )
    return poly


def query_ifc_spaces(g: Graph, elements, model_name, length_unit):
    graph_contents = []
    space_ids = []
    for space, space_type in elements:
        if space_type not in [IFC_CONCEPTS["IFCSPACE"]]:
            continue
        space_id = get_entity_id(g, space, "space")
        space_ids.append(space_id)

        space_placement = g.value(space, IFC_CONCEPTS["objectplacement"])
        space_placement_id = get_entity_id(g, space_placement, "placement")
        logger.info("Processing %s", space_id)
        parent = query_placement_rel_to(g, space_placement)
        space_json = render_ifc_template(
            "ifc/spaces/space-entity.json.jinja",
            space_id=space_id,
            space_ref_frame=space_placement_id,
            model_name=model_name,
            length_unit=length_unit,
        )
        graph_contents.extend(space_json)

        space_reps = query_product_shape_representations(g, space)
        for space_shape in g.objects(space_reps, IFC_CONCEPTS["items"]):
            shape_type = g.value(space_shape, RDF["type"])
            if shape_type == IFC_CONCEPTS["IFCPOLYGONALFACESET"]:
                solid_id = get_entity_id(g, space_shape, "polygonal-face-set")
                # TODO Check if the space frame is needed.
                #  The points could be defined wrt to the space_placement_id directly
                poly = transform_polygonal_face_set(
                    g, space_shape, space_id, length_unit, placement_id=space_id
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
            elif shape_type == IFC_CONCEPTS["IFCFACETEDBREP"]:
                _poly = transform_faceted_brep(
                    g, space_shape, space_id, length_unit, space_id
                )
                graph_contents.extend(_poly)
            else:
                raise ValueError("Unsupported shape: {}".format(shape_type))

    # TODO This is needed because "spaces" in the metamodel has a @list container. It should probably be a set instead
    graph_contents.append({"@id": model_name, "spaces": space_ids})
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

    print()
    qres = g.query(project_units_query)
    assert len(qres) == 1
    return list(qres)[0]


def query_ifc_task_elements(
    g, elements, length_unit, element_types=["IFCOUTLET", "IFCDUCTSEGMENT"]
):
    logger.info("Querying for: {}".format(element_types))
    task_query = """
    SELECT DISTINCT ?wall ?opening 
    WHERE {
        ?wall rdf:type ifc:IFCWALL  .
        ?opening rdf:type ifc:IFCOPENINGELEMENT  .
        
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
    element_types = [IFC_CONCEPTS[e] for e in element_types]

    for element, element_type in elements:
        if element_type not in element_types:
            continue
        # for concept in element_types:
        logger.info("Processing {}s".format(element))
        qres = g.query(q, initBindings={"object": element})
        # logger.info("Total elements: %d", len(qres))
        assert len(list(qres)) == 1
        for wall, opening in qres:
            wall_id = get_entity_id(g, wall, "wall")
            opening_id = get_entity_id(g, opening, "opening")
            object_type = (
                g.namespace_manager.curie(element_type)
                .split(":")[-1]
                .replace("IFC", "")
                .lower()
            )
            # object_id = get_entity_id(g, object, concept.replace("IFC", "").lower())
            object_id = get_entity_id(g, element, object_type)
            logger.info("Processing {}".format(object_id))
            logger.debug(
                "%s <-- voids -- %s <-- fills -- %s", wall_id, opening_id, object_id
            )

            space_placement, plane_pos, plane_shape = query_space_boundary_rel(
                g, element
            )
            plane_id = object_id + "-milling"
            plane_pos = transform_axis_placement_3d(g, plane_pos, plane_id, length_unit)
            graph_contents.extend(plane_pos)
            space_placement_id = get_entity_id(g, space_placement, "placement")
            plane_placement = render_ifc_template(
                "ifc/placement/object-placement.json.jinja",
                placement_id=plane_id,
            )
            graph_contents.extend(plane_placement)
            plane_rel_to = render_ifc_template(
                "ifc/placement/placement-rel-to.json.jinja",
                placement_id=plane_id,
                ref_placement_id=space_placement_id,
            )
            graph_contents.extend(plane_rel_to)
            plane_normal = render_ifc_template(
                "ifc/task-elements/milling-task.json.jinja",
                placement_id=plane_id,
                element_id=plane_id,
                opening_id=opening_id,
                wall_id=wall_id,
                length_unit=length_unit,
            )
            graph_contents.extend(plane_normal)

            opening_placement = g.value(opening, IFC_CONCEPTS["objectplacement"])
            opening_placement_id = get_entity_id(g, opening_placement, "placement")

            opening_reps = query_product_shape_representations(g, opening)
            for rep in g.objects(opening_reps, IFC_CONCEPTS["items"]):
                logger.debug("Shape representation: %s", g.value(rep, RDF["type"]))
                if g.value(rep, RDF["type"]) == IFC_CONCEPTS["IFCEXTRUDEDAREASOLID"]:
                    meas = transform_mapped_extruded_area_solid(
                        g, rep, opening_id, opening_placement_id, length_unit
                    )
                    graph_contents.extend(meas)
                elif g.value(rep, RDF["type"]) == IFC_CONCEPTS["IFCPOLYGONALFACESET"]:
                    poly = transform_polygonal_face_set(
                        g,
                        rep,
                        opening_id,
                        length_unit,
                        placement_id=opening_placement_id,
                    )
                    graph_contents.extend(poly)
                else:
                    transform_unsupported_shapes(g, rep)

    return graph_contents


def query_space_boundary_rel(g: Graph, obj):
    space_boundary_query = """
    SELECT DISTINCT ?boundary ?space_placement ?position ?shape
    WHERE {
        ?boundary rdf:type ifc:IFCRELSPACEBOUNDARY .
        ?boundary ifc:relatedbuildingelement ?object .
        ?boundary ifc:relatingspace/ifc:objectplacement ?space_placement .
        ?boundary ifc:connectiongeometry/ifc:surfaceonrelatingelement ?plane .
        ?plane ifc:basissurface/ifc:position ?position .
        ?plane ifc:outerboundary ?shape .
    }
    """
    q = prepareQuery(space_boundary_query, initNs={"ifc": IFC_CONCEPTS, "rdf": RDF})
    qres = g.query(q, initBindings={"object": obj})
    assert len(qres) == 1
    res = list(qres)[0]
    return res["space_placement"], res["position"], res["shape"]


def stats(g):
    def get_object_type_count(g: Graph, obj_type):
        if isinstance(obj_type, URIRef):
            obj = obj_type
        else:
            obj = IFC_CONCEPTS[obj_type]

        return len(list(g.subjects(RDF["type"], obj)))

    print("\nStats\n-------------")
    print("Total sites: ", get_object_type_count(g, "IFCSITE"))
    print("Total buildings: ", get_object_type_count(g, "IFCBUILDING"))
    print("Total storeys: ", get_object_type_count(g, "IFCBUILDINGSTOREY"))
    print("Total spaces: ", get_object_type_count(g, "IFCSPACE"))
    total_walls = 0
    for wt in WALL_CONCEPTS:
        wall_count = get_object_type_count(g, wt)
        total_walls = total_walls + wall_count
    print("Total walls: ", total_walls)
    print("Total openings: ", get_object_type_count(g, "IFCOPENINGELEMENT"))

    voiding_query = """
    SELECT DISTINCT ?wall ?opening 
    WHERE {
        ?opening rdf:type ifc:IFCOPENINGELEMENT  .
        ?r rdf:type ifc:IFCRELVOIDSELEMENT .
        ?r ifc:relatingbuildingelement ?wall .
        ?r ifc:relatedopeningelement ?opening .
    }
    """

    qres = g.query(voiding_query)
    print("Total openings voiding objects:", len(qres))

    print("Total doors: ", get_object_type_count(g, "IFCDOOR"))
    print("Total outlets: ", get_object_type_count(g, "IFCOUTLET"))
    print("Total ducts: ", get_object_type_count(g, "IFCDUCT"))

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
