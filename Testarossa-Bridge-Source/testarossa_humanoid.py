"""Bounded procedural humanoid blockout generator for Blender 5.3.

Builds one fused metaball-derived mesh. It does not execute user-provided code,
read external files, or choose an output path.
"""
from __future__ import annotations

def validate_dimensions(height, shoulder_width, hip_width, voxel_size):
    values = (height, shoulder_width, hip_width, voxel_size)
    if any(type(v) not in (int, float) for v in values):
        raise ValueError("dimensions_must_be_numeric")
    h, sw, hw, voxel = (float(v) for v in values)
    if not (1.4 <= h <= 2.1):
        raise ValueError("height_out_of_range")
    if not (0.32 <= sw <= 0.62):
        raise ValueError("shoulder_width_out_of_range")
    if not (0.28 <= hw <= 0.52):
        raise ValueError("hip_width_out_of_range")
    if not (0.025 <= voxel <= 0.08):
        raise ValueError("voxel_size_out_of_range")
    return h, sw, hw, voxel


def build_humanoid_blockout(bpy, name, collection, height=1.72,
                            shoulder_width=0.43, hip_width=0.37,
                            voxel_size=0.045):
    h, sw, hw, voxel = validate_dimensions(
        height, shoulder_width, hip_width, voxel_size
    )
    if collection not in bpy.data.collections:
        raise ValueError("target_collection_missing")
    target = bpy.data.collections[collection]

    meta = bpy.data.metaballs.new(name + "_FusionField")
    meta.resolution = min(0.12, max(0.035, voxel * 1.35))
    meta.render_resolution = min(0.08, max(0.025, voxel))
    meta.threshold = 0.62
    field = bpy.data.objects.new(name + "_FusionField", meta)
    target.objects.link(field)

    def blob(x, y, z, sx, sy, sz):
        e = meta.elements.new()
        e.type = "ELLIPSOID"
        e.co = (x, y, z)
        e.radius = 1.0
        e.size_x, e.size_y, e.size_z = sx, sy, sz
        e.stiffness = 2.0
        return e

    def segment(a, b, radius_x, radius_y=None):
        if radius_y is None:
            radius_y = radius_x
        # Dense overlapping spherical metaball samples form an orientation-
        # independent continuous limb, including horizontal forearms/fingers.
        ax, ay, az = a
        bx, by, bz = b
        dx, dy, dz = bx-ax, by-ay, bz-az
        length = (dx*dx + dy*dy + dz*dz) ** 0.5
        spacing = max(min(radius_x, radius_y) * 0.62, voxel * 0.70)
        count = max(2, min(96, int(length / spacing) + 2))
        for index in range(count):
            t = index / (count - 1)
            taper = 0.88 + 0.12 * (1.0 - abs(2.0*t - 1.0))
            x, y, z = ax + dx*t, ay + dy*t, az + dz*t
            blob(x, y, z, radius_x*taper, radius_y*taper,
                 max(radius_x, radius_y)*taper)

    # Coordinates use Z-up, front toward negative Y. All dimensions scale
    # proportionally from the requested overall character height.
    s = h
    shoulder_z, chest_z = .785*s, .735*s
    waist_z, pelvis_z = .625*s, .555*s
    head_z = .915*s

    # Skull, jaw and neck.
    blob(0, 0, head_z, .092*s, .086*s, .112*s)
    blob(0, -.004*s, .855*s, .067*s, .071*s, .061*s)
    blob(0, 0, .805*s, .045*s, .045*s, .055*s)
    segment((0, 0, .805*s), (0, 0, .765*s), .043*s, .043*s)

    # Connected torso with a natural chest-to-waist-to-pelvis transition.
    blob(0, 0, chest_z, .155*s, .092*s, .105*s)
    blob(0, 0, .690*s, .135*s, .078*s, .105*s)
    blob(0, 0, waist_z, .105*s, .070*s, .095*s)
    blob(0, 0, pelvis_z, hw*.48, .092*s, .095*s)
    blob(0, .012*s, .535*s, hw*.43, .094*s, .070*s)

    # Shoulder girdle and both arms in a relaxed T-pose.
    for side in (-1, 1):
        shoulder_x = side * sw*.46
        elbow_x = side * sw*.82
        wrist_x = side * sw*1.08
        palm_x = side * sw*1.18
        blob(shoulder_x, 0, shoulder_z, .082*s, .080*s, .083*s)
        segment((shoulder_x, 0, shoulder_z-.015*s),
                (elbow_x, 0, .735*s), .050*s, .052*s)
        blob(elbow_x, 0, .735*s, .043*s, .043*s, .045*s)
        segment((elbow_x, 0, .735*s),
                (wrist_x, 0, .715*s), .036*s, .038*s)
        blob(palm_x, -.002*s, .712*s, .052*s, .027*s, .040*s)
        # Reinforce the forearm-to-palm transition. At the production voxel
        # resolution the original wrist endpoint can leave a hairline gap;
        # this overlapping bridge keeps the hand rooted in the arm.
        segment((side*sw*.90, -.001*s, .712*s),
                (side*sw*1.20, -.002*s, .712*s), .035*s, .035*s)
        # Four fingers extend outward; their spacing is visible in front view.
        for i in range(4):
            zoff = (1.5-i) * .019*s
            start = (side*sw*1.21, -.004*s, .712*s+zoff)
            end = (side*sw*1.36, -.008*s, .712*s+zoff)
            segment(start, end, .010*s, .010*s)
        # Thumb angles away from the palm instead of becoming a fifth parallel digit.
        segment((side*sw*1.18, -.004*s, .680*s),
                (side*sw*1.30, -.008*s, .665*s), .014*s, .013*s)

    # Legs, knees, calves, ankles and feet. The hip forms overlap the pelvis.
    for side in (-1, 1):
        hip_x = side * hw*.245
        knee_x = side * hw*.255
        ankle_x = side * hw*.27
        blob(hip_x, .006*s, .515*s, .090*s, .087*s, .105*s)
        segment((hip_x, .006*s, .515*s),
                (knee_x, 0, .315*s), .066*s, .070*s)
        blob(knee_x, -.004*s, .315*s, .055*s, .061*s, .052*s)
        segment((knee_x, 0, .315*s),
                (ankle_x, .004*s, .095*s), .045*s, .050*s)
        blob(ankle_x, .002*s, .105*s, .036*s, .040*s, .045*s)
        # Heel and forefoot point forward along negative Y.
        blob(ankle_x, -.035*s, .055*s, .052*s, .085*s, .035*s)
        blob(ankle_x, -.105*s, .045*s, .060*s, .075*s, .032*s)

    # Convert the single fused field to one mesh, then bounded voxel-remesh
    # and smooth it. This produces a coherent sculpting foundation rather
    # than a pile of disconnected primitive objects.
    bpy.context.view_layer.objects.active = field
    field.select_set(True)
    bpy.ops.object.convert(target="MESH")
    body = bpy.context.object
    body.name = name
    body.data.name = name + "_Mesh"
    remesh = body.modifiers.new("Foundation_Voxel_Remesh", "REMESH")
    remesh.mode = "VOXEL"
    remesh.voxel_size = voxel
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.modifier_apply(modifier=remesh.name)
    smooth = body.modifiers.new("Foundation_Soften", "SMOOTH")
    smooth.factor = 1.15
    smooth.iterations = 3
    bpy.ops.object.modifier_apply(modifier=smooth.name)

    if len(body.data.vertices) > 250000:
        raise RuntimeError("humanoid_vertex_budget_exceeded")
    for polygon in body.data.polygons:
        polygon.use_smooth = True
    body["testarossa_asset_role"] = "procedural_humanoid_blockout"
    body["construction_method"] = "fused_metaball_voxel_remesh"
    body["design_height_m"] = h
    body["voxel_size_m"] = voxel
    body["topology_status"] = "blockout_not_production_topology"
    return body
