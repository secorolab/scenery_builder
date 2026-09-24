import os
import bpy
import bmesh
import logging

logger = logging.getLogger("floorplan.transformations.blender")
logger.setLevel(logging.DEBUG)


def create_mesh(collection, name, vertices, faces):
    """Creates a mesh"""

    me = bpy.data.meshes.new(name)
    me.from_pydata(vertices, [], faces)
    me.update()

    bm = bmesh.new()
    bm.from_mesh(me, face_normals=True)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    # Finish up, write the bmesh back to the mesh
    bm.to_mesh(me)
    bm.free()  # free and prevent further access
    me.update()

    obj = bpy.data.objects.new(name, me)
    collection.objects.link(obj)


def create_collection(name):
    """Creates an object collection"""

    collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(collection)
    return collection


def clear_scene():
    """Clears the scene from all objects (often the default objects: a cube mesh, a light source, and a camera)"""

    for obj in bpy.context.scene.objects:
        obj.select_set(True)
        bpy.ops.object.delete()


def boolean_operation_difference(obj_name, cutter_name):
    """Performs the difference boolean operation"""

    # select the object
    obj = bpy.data.objects[obj_name]
    # configure modifier
    boolean = obj.modifiers.new(name="boolean", type="BOOLEAN")
    boolean.object = bpy.data.objects[cutter_name]
    boolean.operation = "DIFFERENCE"
    boolean.solver = "EXACT"
    # apply modifier
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier="boolean")


def create_element_mesh(building, elements):
    for e in elements:
        name = e.get("name")
        vertices = e.get("vertices")
        faces = e.get("faces")
        create_mesh(building, name, vertices, faces)


def union_meshes(collection):
    """Boolean-union every mesh in ``collection`` into a single clean object.

    MuJoCo treats each ``o`` group in an OBJ as a separate mesh; exporting the
    walls/columns as one object (one ``o``) is required for the shell to load
    as a single mesh. A plain join is not enough: adjoining spaces produce
    coplanar, contained, or interpenetrating wall solids (shared walls, corner
    miters), and joining keeps every overlapping face, which z-fights in
    consumers. The union removes the interior geometry and yields one manifold
    shell. Must run after ``subtract_opening`` so doorways are already cut
    through every overlapping wall.
    """

    meshes = [o for o in collection.objects if o.type == "MESH"]
    if len(meshes) < 2:
        return

    # Union every operand into ``target`` in a single modifier over a collection,
    # with ``use_self`` on. Doing all operands at once (rather than a sequential
    # pairwise union) is what actually resolves the coplanar shared-wall faces:
    # pairwise leaves same-facing coplanar remnants that still z-fight, while the
    # collection+self union merges them and cuts visible overlap to zero.
    target = meshes[0]
    operands = bpy.data.collections.new("union_operands")
    bpy.context.scene.collection.children.link(operands)
    for other in meshes[1:]:
        collection.objects.unlink(other)
        operands.objects.link(other)

    boolean = target.modifiers.new(name="boolean", type="BOOLEAN")
    boolean.operand_type = "COLLECTION"
    boolean.collection = operands
    boolean.operation = "UNION"
    boolean.solver = "EXACT"
    boolean.use_self = True
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier="boolean")

    for other in list(operands.objects):
        bpy.data.objects.remove(other, do_unlink=True)
    bpy.data.collections.remove(operands)

    # The boolean does not dissolve interfaces where two wall slabs merely *touch*
    # (a shared wall emitted as two abutting solids butts together with zero
    # overlap volume, so EXACT leaves both coincident interface faces -- still a
    # flicker source, plus unwelded seam vertices and zero-area offcuts from the
    # opening cuts). Merge-by-distance welds the coincident vertices and drops
    # the resulting duplicate faces; dissolving degenerates clears the zero-area
    # offcuts. Together they take coincident verts, degenerate faces, and
    # residual coplanar overlap to zero without closing any doorway.
    bm = bmesh.new()
    bm.from_mesh(target.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-4, edges=bm.edges)
    bm.normal_update()
    bm.to_mesh(target.data)
    bm.free()
    target.data.update()


def project_box_uvs(collection, cube_size=1.0):
    """Write a world-scale box (cube) UV layer to every mesh in ``collection``.

    Done directly with ``bmesh`` instead of ``bpy.ops.uv.cube_project`` because
    that operator fails its context poll under ``blender -b`` (there is no
    ``VIEW_3D`` area in background mode). Each face is projected along the
    dominant world axis of its normal, using the other two world coordinates
    divided by ``cube_size`` as (u, v) -- so ``cube_size=1.0`` gives 1 UV unit
    per meter and textures tile consistently regardless of wall size.
    """

    for obj in collection.objects:
        if obj.type != "MESH":
            continue
        me = obj.data
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.normal_update()
        uv = bm.loops.layers.uv.verify()
        for face in bm.faces:
            nx, ny, nz = (abs(c) for c in face.normal)
            for loop in face.loops:
                x, y, z = loop.vert.co
                if nx >= ny and nx >= nz:  # face ~ perpendicular to X
                    u, v = y, z
                elif ny >= nx and ny >= nz:  # perpendicular to Y
                    u, v = x, z
                else:  # perpendicular to Z
                    u, v = x, y
                loop[uv].uv = (u / cube_size, v / cube_size)
        bm.to_mesh(me)
        bm.free()
        me.update()


def subtract_opening(openings):
    # boolean operation for walls and opening
    for opening in openings:
        name = opening.get("name")
        for wall in opening.get("voids", list()):
            boolean_operation_difference(wall, name)
        bpy.data.objects[name].select_set(True)
        bpy.ops.object.delete()


def main(elements):
    model_name = elements.get("model_name")
    building = create_collection(model_name)
    # clear the blender scene
    clear_scene()

    walls = elements.get("walls", [])
    create_element_mesh(building, walls)

    columns = elements.get("columns", [])
    create_element_mesh(building, columns)

    dividers = elements.get("dividers", [])
    create_element_mesh(building, dividers)

    doors = elements.get("doors", [])
    create_element_mesh(building, doors)

    door_linings = elements.get("door_linings", [])
    create_element_mesh(building, door_linings)

    entryways = elements.get("entryways", [])
    create_element_mesh(building, entryways)
    subtract_opening(entryways)

    windows = elements.get("windows", [])
    create_element_mesh(building, windows)
    subtract_opening(windows)

    # Union + UVs are only needed for OBJ export; doing them once here (after
    # the boolean cuts, so both match the final geometry) keeps the STL/glTF-only
    # paths unchanged. MuJoCo needs a single manifold mesh with its own texcoords.
    wants_obj = any(
        fn.lower().endswith(".obj") for _, fn in elements.get("output_files", [])
    )
    if wants_obj:
        union_meshes(building)
        project_box_uvs(building)

    output_files = []
    for output_path, file_name in elements.get("output_files", []):
        f = save_file(file_name, output_path)
        output_files.append(f)

    return output_files


def save_file(file_name, output_path):
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    base_name, ext = os.path.splitext(file_name)
    output_file = os.path.abspath(os.path.join(output_path, file_name))

    if ext in [".stl"]:
        bpy.ops.wm.stl_export(filepath=output_file)
    elif ext in [".dae"]:
        bpy.ops.wm.collada_export(filepath=output_file)
    elif ext in [".gltf", ".glb"]:
        bpy.ops.export_scene.gltf(filepath=output_file)
    elif ext in [".obj"]:
        # Keep coordinates identical to the STL export (Blender-native Z-up, no
        # reorientation) and carry the box UVs. Materials/textures are declared
        # in the MJCF, not the OBJ, so skip material export.
        bpy.ops.wm.obj_export(
            filepath=output_file,
            export_uv=True,
            export_normals=True,
            export_materials=False,
            forward_axis="Y",
            up_axis="Z",
        )

    logger.info(f"Generated {output_file}")
    return output_file


if __name__ == "__main__":
    import json
    import sys

    args = sys.argv
    with open(args[-1], "r") as f:
        elements = json.load(f)

    main(elements)
