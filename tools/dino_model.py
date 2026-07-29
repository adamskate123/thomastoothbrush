"""
Builds the plush dinosaur character for the toothbrush timer and exports it as
glTF (.glb), which gets inlined into index.html as a data URI.

Run headless:
    blender --background --python tools/dino_model.py -- [out.glb]

Why Blender rather than assembling primitives in Three.js: the mouth needs to be
a real opening cut out of one connected head. Stacking stretched spheres reads as
separate floating pieces no matter how they are tuned. Here the cavity is a
boolean difference and the surface is smoothed with subdivision, so the head is
genuinely one form with a hole in it.

Every tooth is exported as its own named object (tooth_UR_0 ... tooth_LL_4)
because the app recolours teeth individually as they get brushed.
"""

import bpy
import bmesh
import math
import os
import sys
from mathutils import Vector

# ----------------------------------------------------------------------------
# proportions (Blender units; the head is roughly 2 units wide)
# ----------------------------------------------------------------------------
HEAD_W, HEAD_H, HEAD_D = 1.06, 1.00, 0.92     # head half-extents
MOUTH_CY = -0.14                               # centre of the mouth opening
MOUTH_W, MOUTH_H, MOUTH_D = 0.86, 0.42, 1.10   # cutter half-extents
JAW_TOP = MOUTH_CY + MOUTH_H                   # upper arch gum line
JAW_BOT = MOUTH_CY - MOUTH_H                   # lower arch gum line

ARC_A, ARC_B = 0.62, 0.54                      # tooth arch radii (x, z)
TOOTH_W = [0.20, 0.18, 0.17, 0.18, 0.20]       # full widths, front -> back
TOOTH_H = [0.20, 0.18, 0.17, 0.15, 0.135]      # crown lengths
QUADS = ["UR", "UL", "LL", "LR"]               # matches QUADS[] in index.html

MINT = (0.62, 0.83, 0.72, 1.0)
MINT_DEEP = (0.48, 0.72, 0.61, 1.0)
CREAM = (0.95, 0.90, 0.81, 1.0)
ROSE_DEEP = (0.55, 0.30, 0.36, 1.0)
GUM = (0.85, 0.58, 0.63, 1.0)
TONGUE = (0.90, 0.63, 0.67, 1.0)
TOOTH = (1.0, 0.99, 0.97, 1.0)
EYE_DARK = (0.16, 0.22, 0.27, 1.0)
WHITE = (1.0, 1.0, 1.0, 1.0)
BLUSH = (0.93, 0.64, 0.68, 1.0)


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def make_material(name, rgba, roughness=0.95):
    """Felt: fully rough, zero metalness, so there is no specular hotspot."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = 0.0
    return mat


def add_uv_sphere(name, loc, scale, segments=32, rings=18, smooth=True):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments, ring_count=rings, radius=1.0, location=loc
    )
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = scale
    if smooth:
        bpy.ops.object.shade_smooth()
    return ob


def apply_all_modifiers(ob):
    bpy.context.view_layer.objects.active = ob
    for m in list(ob.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)


def fix_normals(ob):
    """Boolean solvers routinely leave flipped faces. Without this the head
    renders inside-out in three.js: you see the far inner surface as a pale
    dome floating in front of everything."""
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")


def assign(ob, mat):
    ob.data.materials.clear()
    ob.data.materials.append(mat)


# ----------------------------------------------------------------------------
# head with a real mouth cavity
# ----------------------------------------------------------------------------
def build_head(mat_body, mat_inner):
    """Builds the head, then derives the mouth cavity and tooth arch from its
    MEASURED size.

    Everything downstream is proportional to the real head. Hand-tuning the
    cavity and the arch as independent constants kept putting them out of sync
    — first the cavity was smaller than the arch (teeth buried behind the face),
    then wider than the head itself (the boolean sliced the head in two).
    """
    # A subdivided cube gives far better topology for a boolean than a UV
    # sphere (no pole pinching at the cut).
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
    head = bpy.context.active_object
    head.name = "head"
    head.scale = (HEAD_W, HEAD_D, HEAD_H)     # Blender: Z is up, Y is depth
    bpy.ops.object.transform_apply(scale=True)

    sub = head.modifiers.new("sub", "SUBSURF")
    sub.levels = sub.render_levels = 2
    apply_all_modifiers(head)

    # Measure what subsurf actually produced — it pulls a cube well inside its
    # nominal scale, so the constants above are not the real extents.
    side, front, top = head_bounds(head)

    g = {
        "side": side, "front": front, "top": top,
        "cw": side * 0.72,             # cavity half-width, safely inside the head
        "ch": top * 0.36,              # cavity half-height
        "cy": -top * 0.10,             # cavity centre (slightly below middle)
    }
    g["jaw_top"] = g["cy"] + g["ch"]
    g["jaw_bot"] = g["cy"] - g["ch"]
    g["arc_a"] = g["cw"] * 0.88        # tooth arch stays inside the cavity
    g["arc_b"] = abs(front) * 0.16   # near-flat arch: every tooth stays in the
                                     # visible aperture instead of wrapping back
                                     # behind the face

    # Mouth cutter: rounded with BEVEL, not SUBSURF — subsurf shrinks a cube
    # toward its inscribed sphere (~25% at level 2).
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, front * 0.55, g["cy"]))
    cutter = bpy.context.active_object
    cutter.name = "mouth_cutter"
    cutter.scale = (g["cw"], abs(front) * 1.4, g["ch"])
    bpy.ops.object.transform_apply(scale=True)
    cbev = cutter.modifiers.new("bevel", "BEVEL")
    cbev.width = min(g["cw"], g["ch"]) * 0.42
    cbev.segments = 6
    cbev.limit_method = "ANGLE"
    apply_all_modifiers(cutter)

    # cut the opening out of the head
    bpy.context.view_layer.objects.active = head
    boolean = head.modifiers.new("mouth", "BOOLEAN")
    boolean.operation = "DIFFERENCE"
    boolean.object = cutter
    boolean.solver = "EXACT"
    apply_all_modifiers(head)
    bpy.data.objects.remove(cutter, do_unlink=True)
    fix_normals(head)

    bpy.context.view_layer.objects.active = head
    bpy.ops.object.shade_smooth()
    assign(head, mat_body)

    # Inner mouth shell: sits behind the teeth so you see soft rose lining
    # through the opening rather than straight through the head.
    inner = add_uv_sphere("mouth_inner", (0, abs(front) * 0.62, g["cy"]),
                          (g["cw"] * 0.98, abs(front) * 0.55, g["ch"] * 0.98))
    assign(inner, mat_inner)
    print(f"[dino_model] head half-extents  side={side:.2f} front={front:.2f} top={top:.2f}")
    print(f"[dino_model] cavity cw={g['cw']:.2f} ch={g['ch']:.2f}  arch a={g['arc_a']:.2f} b={g['arc_b']:.2f}")
    return head, inner, g


# ----------------------------------------------------------------------------
# teeth
# ----------------------------------------------------------------------------
def build_teeth(mat_tooth, g):
    """One rounded box per tooth, placed on the measured arch and named per
    quadrant. Widths are scaled so five teeth span ~85 deg of the arch, which
    keeps them inside the cavity whatever size the head ended up."""
    arc_a, arc_b = g["arc_a"], g["arc_b"]
    span = 1.48                                    # radians per quadrant
    shape = [1.0, 0.90, 0.85, 0.92, 1.02]          # relative tooth widths
    unit = (span * arc_a) / sum(shape)
    widths = [r * unit for r in shape]
    depth = g["ch"] * 0.92
    heights = [depth * r for r in (1.0, 0.90, 0.85, 0.76, 0.68)]

    teeth = []
    for quad in QUADS:
        upper = quad[0] == "U"
        side = 1 if quad[1] == "R" else -1         # +1 = the child's right
        th = 0.04
        for i in range(5):
            w, h = widths[i], heights[i]
            th += (w / 2) / arc_a
            x = side * arc_a * math.sin(th)
            y = -arc_b * math.cos(th)              # -Y is toward the viewer
            z = (g["jaw_top"] - h / 2) if upper else (g["jaw_bot"] + h / 2)

            bpy.ops.mesh.primitive_cube_add(size=2, location=(x, y, z))
            t = bpy.context.active_object
            t.name = f"tooth_{quad}_{i}"
            t.scale = (w / 2, w * 0.36, h / 2)
            bpy.ops.object.transform_apply(scale=True)
            t.rotation_euler = (0, 0, -side * th)

            bev = t.modifiers.new("bevel", "BEVEL")
            bev.width = min(w, h) * 0.26
            bev.segments = 3
            bev.limit_method = "ANGLE"
            apply_all_modifiers(t)
            bpy.context.view_layer.objects.active = t
            bpy.ops.object.shade_smooth()
            assign(t, mat_tooth)
            teeth.append(t)
            th += (w / 2) / arc_a
    return teeth


def build_gums(mat_gum, g):
    """Soft ridge running along each arch, hiding the tooth roots."""
    gums = []
    for upper in (True, False):
        z = (g["jaw_top"] + 0.012) if upper else (g["jaw_bot"] - 0.012)
        bpy.ops.mesh.primitive_torus_add(
            location=(0, 0, z),
            major_radius=1.0, minor_radius=0.055,
            major_segments=56, minor_segments=10,
        )
        gm = bpy.context.active_object
        gm.name = "gum_upper" if upper else "gum_lower"
        gm.scale = (g["arc_a"] + 0.02, g["arc_b"] + 0.02, 1.0)
        bpy.ops.object.transform_apply(scale=True)
        bpy.ops.object.shade_smooth()
        assign(gm, mat_gum)
        gums.append(gm)
    return gums


# ----------------------------------------------------------------------------
# face
# ----------------------------------------------------------------------------
def head_bounds(head):
    """Real extents after subdivision. Subsurf pulls a cube well inside its
    original scale, so features placed against the nominal HEAD_* constants end
    up floating off the surface. Measure instead of assuming."""
    xs = [head.matrix_world @ Vector(c) for c in head.bound_box]
    return (max(v.x for v in xs), min(v.y for v in xs), max(v.z for v in xs))


def build_face(mats, head, g):
    parts = []
    side, front, top = g["side"], g["front"], g["top"]
    eye_z = top - 0.16
    eye_y = front * 0.42
    for sx in (-1, 1):
        turret = add_uv_sphere(f"turret_{sx}", (sx * side * 0.52, eye_y * 0.5, eye_z),
                               (0.34, 0.34, 0.34))
        assign(turret, mats["body"])
        white = add_uv_sphere(f"eyewhite_{sx}", (sx * side * 0.54, eye_y, eye_z + 0.03),
                              (0.225, 0.225, 0.225))
        assign(white, mats["white"])
        pupil = add_uv_sphere(f"pupil_{sx}", (sx * side * 0.56, eye_y - 0.14, eye_z + 0.02),
                              (0.14, 0.14, 0.14))
        assign(pupil, mats["dark"])
        glint = add_uv_sphere(f"glint_{sx}", (sx * side * 0.60, eye_y - 0.20, eye_z + 0.10),
                              (0.052, 0.052, 0.052), 16, 10)
        assign(glint, mats["white"])
        blush = add_uv_sphere(f"blush_{sx}", (sx * side * 0.74, front * 0.62, g["cy"] + g["ch"] * 0.9),
                              (0.18, 0.10, 0.11), 20, 12)
        assign(blush, mats["blush"])
        nostril = add_uv_sphere(f"nostril_{sx}", (sx * 0.15, front * 0.92, g["jaw_top"] + top * 0.44),
                                (0.05, 0.05, 0.038), 16, 10)
        assign(nostril, mats["deep"])
        parts += [turret, white, pupil, glint, blush, nostril]

    # cream muzzle patch above the mouth, kept clear of the opening
    patch = add_uv_sphere("muzzle", (0, front * 0.90, g["jaw_top"] + top * 0.30), (0.38, 0.14, 0.15))
    assign(patch, mats["cream"])
    parts.append(patch)

    # tongue, low inside the mouth
    tongue = add_uv_sphere("tongue", (0, -0.20, g["jaw_bot"] + g["ch"] * 0.22),
                           (g["arc_a"] * 0.72, abs(front) * 0.34, g["ch"] * 0.16))
    assign(tongue, mats["tongue"])
    parts.append(tongue)

    # back scutes
    for i, sx in enumerate((-0.30, 0.0, 0.30)):
        r = 0.15 if sx != 0 else 0.17
        s = add_uv_sphere(f"scute_{i}", (sx, 0.10, top - 0.04 + (0.03 if sx == 0 else 0)),
                          (r, r, r), 20, 12)
        assign(s, mats["deep"])
        parts.append(s)
    return parts


def main():
    reset_scene()
    mats = {
        "body": make_material("felt_body", MINT, 0.97),
        "deep": make_material("felt_deep", MINT_DEEP, 0.97),
        "cream": make_material("felt_cream", CREAM, 0.95),
        "inner": make_material("mouth_inner", ROSE_DEEP, 1.0),
        "gum": make_material("gum", GUM, 0.95),
        "tongue": make_material("tongue", TONGUE, 0.9),
        "tooth": make_material("tooth", TOOTH, 0.45),
        "white": make_material("eye_white", WHITE, 0.5),
        "dark": make_material("eye_dark", EYE_DARK, 0.4),
        "blush": make_material("blush", BLUSH, 1.0),
    }

    head, _inner, g = build_head(mats["body"], mats["inner"])
    build_gums(mats["gum"], g)
    build_teeth(mats["tooth"], g)
    build_face(mats, head, g)

    out = "assets/dino.glb"
    argv = sys.argv
    if "--" in argv:
        extra = argv[argv.index("--") + 1:]
        if extra:
            out = extra[0]
    out = os.path.abspath(out)
    os.makedirs(os.path.dirname(out), exist_ok=True)

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(
        filepath=out,
        export_format="GLB",
        export_apply=True,
        export_yup=True,          # glTF/three.js convention: Y up
        use_selection=True,
    )
    size = os.path.getsize(out)
    print(f"[dino_model] wrote {out}  ({size/1024:.0f} KB)")
    names = sorted(o.name for o in bpy.data.objects if o.name.startswith("tooth_"))
    print(f"[dino_model] {len(names)} teeth exported, e.g. {names[:3]}")


if __name__ == "__main__":
    main()
