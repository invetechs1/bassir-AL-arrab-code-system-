"""Render the same villa with Blender's Cycles instead of POV-Ray.

The file is deliberately not called cycles.py: Blender ships its own `cycles`
addon module, and that name shadows this one for anything that imports it.

POV-Ray 3.7 predates microfacet shading: its `finish` is Phong-ish, its sky
is whatever gradient you write, and it has no denoiser, so every sample has
to be paid for. Cycles gives three things that were out of reach there - a
Principled BSDF (GGX microfacet with a real roughness/metallic/IOR
parameterisation), the Nishita physical sun-and-sky model standing in for an
HDRI, and OpenImageDenoise, which buys clean output at a fraction of the
samples.

What it does not change is the source of truth. The geometry, the room
program and the component library stay exactly where they are; this reads
back the solids `library.py` already emitted, through `povparse`, so a sofa
cannot differ between the two renderers.

    blender -b --python tools/render/blender_render.py -- --view majlis-ground \\
        --out out.png --width 1920 --height 1200 --samples 220
"""
import json, math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy
import povparse

# ---------------------------------------------------------------- materials
# base colour, roughness, metallic, and whether it transmits.
# Tuned to the POV-Ray library so the two renderers describe one building.
MATS = {
    "M_Wood":       ((0.337, 0.235, 0.145), 0.34, 0.0),
    "M_WoodDark":   ((0.158, 0.106, 0.068), 0.30, 0.0),
    "M_Fabric":     ((0.560, 0.552, 0.524), 0.72, 0.0),
    "M_FabricAlt":  ((0.492, 0.494, 0.476), 0.70, 0.0),
    "M_Majlis":     ((0.246, 0.312, 0.286), 0.68, 0.0),
    "M_MajlisAlt":  ((0.206, 0.268, 0.246), 0.68, 0.0),
    "M_Cushion":    ((0.262, 0.196, 0.138), 0.66, 0.0),
    "M_CushionAlt": ((0.418, 0.372, 0.296), 0.68, 0.0),
    "M_Throw":      ((0.352, 0.268, 0.196), 0.78, 0.0),
    "M_Lacquer":    ((0.905, 0.898, 0.882), 0.12, 0.0),
    "M_Carcass":    ((0.812, 0.800, 0.780), 0.42, 0.0),
    "M_Metal":      ((0.620, 0.630, 0.645), 0.22, 1.0),
    "M_Steel":      ((0.560, 0.570, 0.580), 0.28, 1.0),
    "M_Brass":      ((0.560, 0.442, 0.222), 0.24, 1.0),
    "M_Mattress":   ((0.900, 0.895, 0.885), 0.70, 0.0),
    "M_Duvet":      ((0.905, 0.900, 0.890), 0.72, 0.0),
    "M_DuvetFold":  ((0.870, 0.866, 0.856), 0.72, 0.0),
    "M_Pillow":     ((0.940, 0.936, 0.928), 0.74, 0.0),
    "M_Curtain":    ((0.888, 0.872, 0.834), 0.76, 0.0),
    "M_Rug":        ((0.352, 0.352, 0.336), 0.88, 0.0),
    "M_RugField":   ((0.300, 0.362, 0.336), 0.88, 0.0),
    "M_Stone":      ((0.760, 0.752, 0.735), 0.18, 0.0),
    "M_Sanitary":   ((0.955, 0.958, 0.960), 0.10, 0.0),
    "M_Appliance":  ((0.700, 0.706, 0.714), 0.20, 0.8),
    "M_Splash":     ((0.830, 0.845, 0.850), 0.08, 0.0),
    "M_Screen":     ((0.030, 0.032, 0.036), 0.18, 0.0),
    "M_Shade":      ((0.920, 0.910, 0.890), 0.62, 0.0),
    "M_Cord":       ((0.090, 0.090, 0.095), 0.52, 0.0),
    "M_Frame":      ((0.155, 0.150, 0.145), 0.38, 0.0),
    "M_Art":        ((0.520, 0.500, 0.470), 0.60, 0.0),
    "M_Pot":        ((0.512, 0.400, 0.320), 0.56, 0.0),
    "M_Foliage":    ((0.246, 0.382, 0.222), 0.44, 0.0),
    "M_Stem":       ((0.236, 0.300, 0.170), 0.52, 0.0),
    "M_Ceramic":    ((0.812, 0.782, 0.726), 0.14, 0.0),
    "M_CeramicDark":((0.196, 0.212, 0.206), 0.10, 0.0),
    "M_Paper":      ((0.880, 0.868, 0.840), 0.80, 0.0),
    "M_BookA":      ((0.352, 0.146, 0.126), 0.52, 0.0),
    "M_BookB":      ((0.180, 0.226, 0.268), 0.52, 0.0),
    "M_BookC":      ((0.760, 0.736, 0.690), 0.56, 0.0),
    "M_Seat":       ((0.360, 0.440, 0.400), 0.70, 0.0),
    "M_Bulb":       ((1.000, 0.960, 0.900), 0.40, 0.0),
    "T_Wall":       ((0.928, 0.918, 0.900), 0.62, 0.0),
    "T_White":      ((0.955, 0.960, 0.958), 0.34, 0.0),
    "T_Ceiling":    ((0.950, 0.945, 0.935), 0.70, 0.0),
    "T_Floor":      ((0.760, 0.748, 0.726), 0.14, 0.0),
    "T_Stone":      ((0.780, 0.772, 0.755), 0.16, 0.0),
    "T_Wood":       ((0.337, 0.235, 0.145), 0.34, 0.0),
    "T_FabricGreen":((0.360, 0.440, 0.400), 0.70, 0.0),
    "T_FabricGrey": ((0.620, 0.618, 0.606), 0.72, 0.0),
    "T_Hedge":      ((0.150, 0.206, 0.122), 0.70, 0.0),
    "T_Far":        ((0.640, 0.612, 0.572), 0.74, 0.0),
    "T_Frond":      ((0.212, 0.276, 0.156), 0.48, 0.0),
    "T_Trunk":      ((0.300, 0.246, 0.180), 0.66, 0.0),
}
GLASS = {"T_Glass", "M_Glass"}
EMIT = {"M_Bulb": 14.0}
_cache = {}


def material(name):
    if name in _cache:
        return _cache[name]
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    if name in GLASS:
        bsdf.inputs["Base Color"].default_value = (0.96, 0.99, 0.97, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.0
        bsdf.inputs["Transmission Weight"].default_value = 1.0
        bsdf.inputs["IOR"].default_value = 1.52
    else:
        col, rough, metal = MATS.get(name, ((0.72, 0.72, 0.70), 0.55, 0.0))
        bsdf.inputs["Base Color"].default_value = (*col, 1.0)
        bsdf.inputs["Roughness"].default_value = rough
        bsdf.inputs["Metallic"].default_value = metal
        if rough >= 0.65 and metal == 0.0:      # cloth catches a rim of sheen
            bsdf.inputs["Sheen Weight"].default_value = 0.22
            bsdf.inputs["Sheen Roughness"].default_value = 0.35
        if name in EMIT:
            bsdf.inputs["Emission Color"].default_value = (1.0, 0.95, 0.88, 1.0)
            bsdf.inputs["Emission Strength"].default_value = EMIT[name]
    _cache[name] = m
    return m


# ---------------------------------------------------------------- geometry
def P(v):
    """POV-Ray to Blender axes.

    The library writes <plan_x, height, plan_y> because POV-Ray is y-up and
    left-handed. Blender is z-up and right-handed, so swapping the last two
    components converts the position and fixes the handedness in one step -
    no scene-wide pivot, and every coordinate is already right when the mesh
    is created.
    """
    return (v[0], v[2], v[1])


def _apply(obj, node):
    """POV applies scale, then translate, in the order written."""
    for sc in node.get("scale", []):
        b = P(sc)
        obj.scale = tuple(obj.scale[i] * b[i] for i in range(3))
    if node.get("rotate"):
        # nothing the component library emits rotates; refuse rather than
        # place a piece of furniture at a silently wrong angle
        raise povparse.ParseError("rotate is not mapped to Blender axes yet")
    for tr in node.get("translate", []):
        b = P(tr)
        obj.location = tuple(obj.location[i] + b[i] for i in range(3))


def _primitive(node):
    """One POV solid as a Blender object, still in POV's y-up frame."""
    t = node["type"]
    if t == "box":
        lo, hi = P(node["lo"]), P(node["hi"])
        bpy.ops.mesh.primitive_cube_add(size=1)
        o = bpy.context.active_object
        o.scale = tuple(abs(hi[i] - lo[i]) or 1e-4 for i in range(3))
        o.location = tuple((hi[i] + lo[i]) / 2 for i in range(3))
    elif t in ("cylinder", "cone"):
        a, b = P(node["a"]), P(node["b"])
        d = [b[i] - a[i] for i in range(3)]
        length = math.sqrt(sum(x * x for x in d)) or 1e-4
        if t == "cylinder":
            bpy.ops.mesh.primitive_cylinder_add(vertices=28, radius=node["r"],
                                                depth=length)
        else:
            bpy.ops.mesh.primitive_cone_add(vertices=28, radius1=node["ra"],
                                            radius2=node["rb"], depth=length,
                                            end_fill_type="NOTHING"
                                            if node.get("open") else "NGON")
        import mathutils
        o = bpy.context.active_object
        o.location = tuple((a[i] + b[i]) / 2 for i in range(3))
        # the primitive is built along +Z; swing it onto a -> b
        o.rotation_mode = "XYZ"
        o.rotation_euler = mathutils.Vector((0, 0, 1)).rotation_difference(
            mathutils.Vector(d).normalized()).to_euler()
    elif t == "sphere":
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=14,
                                             radius=node["r"])
        o = bpy.context.active_object
        o.location = P(node["c"])
    elif t == "superellipsoid":
        # a rounded box; a subdivided cube with a bevel is the closest Cycles
        # equivalent and keeps the silhouette the upholstery needs
        bpy.ops.mesh.primitive_cube_add(size=2)
        o = bpy.context.active_object
        b = o.modifiers.new("bevel", "BEVEL")
        b.width = min(0.18, max(0.02, node["e"][0] * 0.5))
        b.segments = 3
        b.limit_method = "ANGLE"
    else:
        raise povparse.ParseError(f"cannot build {t!r}")
    _apply(o, node)
    return o


def build(node, mat):
    """A parsed shape tree as one Blender object."""
    t = node["type"]
    if t in ("union", "merge", "difference"):
        kids = [build(k, mat) for k in node["children"]]
        kids = [k for k in kids if k]
        if not kids:
            return None
        base = kids[0]
        if t == "difference":
            for k in kids[1:]:
                m = base.modifiers.new("cut", "BOOLEAN")
                m.operation, m.object, m.solver = "DIFFERENCE", k, "FAST"
                k.hide_render = True
        else:
            for k in kids[1:]:
                m = base.modifiers.new("join", "BOOLEAN")
                m.operation, m.object, m.solver = "UNION", k, "FAST"
                k.hide_render = True
        _apply(base, node)
        return base
    o = _primitive(node)
    o.data.materials.append(material(mat))
    return o


def add(geo, mat):
    for node in povparse.parse(geo):
        build(node, mat)


# ---------------------------------------------------------------- the scene
def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def sky(sun_rot=(math.radians(52), 0.0, math.radians(214)), strength=1.0):
    """Nishita physical sun and sky, standing in for an HDRI.

    POV-Ray had a hand-written gradient, so every reflection and every bounce
    carried a sky that does not exist. This is an atmospheric model: the
    horizon, the sun's disc and the colour of the light all follow from the
    sun angle.
    """
    w = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    tex = nt.nodes.new("ShaderNodeTexSky")
    tex.sky_type = "NISHITA"
    tex.sun_elevation = math.radians(54)
    tex.sun_rotation = math.radians(214)
    tex.altitude = 600               # Riyadh sits about 600 m up
    tex.air_density = 0.9
    tex.dust_density = 2.2           # the desert haze the gradient could not give
    bg.inputs["Strength"].default_value = strength
    nt.links.new(tex.outputs[0], bg.inputs[0])
    nt.links.new(bg.outputs[0], out.inputs[0])

    s = bpy.data.lights.new("sun", "SUN")
    s.energy = 5.2
    s.angle = math.radians(0.53)     # the sun's real angular diameter
    s.color = (1.0, 0.95, 0.88)
    o = bpy.data.objects.new("sun", s)
    o.rotation_euler = sun_rot
    bpy.context.collection.objects.link(o)


def ground(W, D):
    bpy.ops.mesh.primitive_plane_add(size=400, location=(W / 2, D / 2, -0.19))
    bpy.context.active_object.data.materials.append(material("T_Far"))


def portals(level, glass_rects):
    """A light portal in every window opening.

    Without them the sampler fires rays into the room and almost none find
    their way out through a window, so the interior comes back black however
    long it runs - the median of a 64-sample frame was exactly zero. A portal
    tells Cycles where the light actually gets in. It is the same device the
    POV-Ray scene uses, and like those it emits nothing itself.
    """
    made = []
    for x, y, w, d, z0, z1, side in glass_rects:
        lamp = bpy.data.lights.new(f"portal-{side}", "AREA")
        lamp.shape = "RECTANGLE"
        lamp.cycles.is_portal = True
        horiz = side in ("n", "s")
        lamp.size = max(w if horiz else d, 0.05)
        lamp.size_y = max(z1 - z0, 0.05)
        o = bpy.data.objects.new(f"portal-{side}", lamp)
        o.location = (x + w / 2, y + d / 2, (z0 + z1) / 2)
        # the portal must face into the room: an area light points down -Z,
        # so stand it upright and turn it to the wall's inward normal
        yaw = {"n": 0.0, "s": math.pi, "w": math.pi / 2, "e": -math.pi / 2}[side]
        o.rotation_euler = (math.radians(90), 0.0, yaw)
        bpy.context.collection.objects.link(o)
        made.append(o)
    return made


def camera(eye, look, angle_deg):
    cam = bpy.data.cameras.new("cam")
    cam.lens_unit = "FOV"
    cam.angle = math.radians(angle_deg)
    o = bpy.data.objects.new("cam", cam)
    bpy.context.collection.objects.link(o)
    bpy.context.scene.camera = o
    import mathutils
    e = mathutils.Vector(eye)
    d = (mathutils.Vector(look) - e)
    o.location = e
    o.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return o


def main(argv):
    import argparse, re, time
    ap = argparse.ArgumentParser()
    ap.add_argument("--view", default="majlis-ground")
    ap.add_argument("--out", default="cycles.png",
                    help="grade target; this writes the .hdr beside it")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1200)
    ap.add_argument("--samples", type=int, default=200)
    args = ap.parse_args(argv)

    import scene as SC
    import render as RD
    view = next(v for v in RD.VIEWS if v[0] == args.view)
    _, level, room, kw = view
    cam_str = SC.camera_for(level, room, **kw)
    m = re.search(r"location <([-\d.]+),([-\d.]+),([-\d.]+)> "
                  r"look_at <([-\d.]+),([-\d.]+),([-\d.]+)> angle ([\d.]+)", cam_str)
    eye = P(tuple(float(m.group(i)) for i in (1, 2, 3)))
    look = P(tuple(float(m.group(i)) for i in (4, 5, 6)))
    fov = float(m.group(7))

    clear()
    W, D, CEIL = SC.W, SC.D, SC.CEIL
    sky()
    ground(W, D)

    # slab and ceiling
    add(SC.box(-0.3, -0.3, W + 0.6, D + 0.6, -0.18, 0.004), "T_Floor")
    add(SC.box(-0.3, -0.3, W + 0.6, D + 0.6, CEIL, CEIL + 0.22), "T_Ceiling")

    # walls, with the door and window voids cut out
    voids = [SC.box(x, y, w, d, z0, z1)
             for x, y, w, d, z0, z1 in SC.openings(level)]
    for x, y, w, d in SC.wall_runs(level):
        run = SC.box(x, y, w, d, 0, CEIL)
        add("difference { " + run + " " + " ".join(voids) + " }", "T_Wall")
    glass_rects = list(SC.glass(level))
    for x, y, w, d, z0, z1, side in glass_rects:
        add(SC.box(x, y, w, d, z0, z1), "T_Glass")
    portals(level, glass_rects)

    # furniture, straight out of the component library
    rooms = SC.G[level]["rooms"]
    for b in SC.G[level]["furn"]:
        res = SC.place(b, rooms, SC.G[level]["furn"])
        if res is None:
            continue
        codes, pieces = res
        rr = SC.room_of(b, rooms)
        ctr = SC._centre(rr) if rr else (b["x"], b["y"])
        fc = SC.LIB.facing_side(b["x"], b["y"], b["w"], b["d"], ctr)
        for code in codes:
            hd = (SC.LIB.facing_side(b["x"], b["y"], b["w"], b["d"],
                                     (ctr[0], ctr[1] - 99))
                  if code.startswith("BED") else None)
            pieces = list(pieces) + SC.dress(code, b, rr, fc, hd)
        for geo, tex in pieces:
            if geo:
                add(geo, tex)
    for geo, tex in SC.corner_props(level, rooms, SC.G[level]["furn"], (eye[0], eye[1])):
        if geo:
            add(geo, tex)

    camera(eye, look, fov)

    s = bpy.context.scene
    s.render.engine = "CYCLES"
    s.cycles.device = "CPU"
    s.cycles.samples = args.samples
    # Distribution builds of Blender are often compiled without
    # OpenImageDenoise, and asking for it then fails at render time rather
    # than at setup. Probe once and say which path is being taken, because
    # the sample count that looks clean differs by roughly a factor of four.
    s.cycles.use_denoising = True
    s.cycles.max_bounces = 8
    s.cycles.caustics_reflective = False
    s.cycles.caustics_refractive = True
    s.render.resolution_x = args.width
    s.render.resolution_y = args.height
    s.render.resolution_percentage = 100
    s.render.film_transparent = False
    # Write linear Radiance, not a tone-mapped PNG, and put it through the
    # very same grade the POV-Ray path uses - including the auto-metering.
    # Any difference left between the two images is then the renderer, which
    # is the only thing worth comparing.
    hdr_path = os.path.splitext(os.path.abspath(args.out))[0] + ".hdr"
    s.render.filepath = hdr_path
    s.render.image_settings.file_format = "HDR"
    s.view_settings.view_transform = "Standard"
    s.view_settings.look = "None"

    # Distribution builds are often compiled without OpenImageDenoise, and
    # asking for it fails at render time, not at setup. Probe with a frame a
    # few pixels across, because the sample count that looks clean differs by
    # roughly four times between the two paths.
    keep = s.render.resolution_percentage
    s.render.resolution_percentage = 1
    try:
        bpy.ops.render.render(write_still=False)
        print("cycles: OpenImageDenoise available", flush=True)
    except RuntimeError as exc:
        if "OpenImageDenoiser" not in str(exc):
            raise
        s.cycles.use_denoising = False
        print("cycles: build has no OpenImageDenoise; rendering undenoised, "
              "so samples carry the whole burden", flush=True)
    s.render.resolution_percentage = keep

    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    took = time.time() - t0
    written = hdr_path if os.path.exists(hdr_path) else hdr_path + "0001.hdr"
    print(f"cycles {args.view}: {args.samples} samples in {took:.0f}s "
          f"-> {written}", flush=True)
    print("CYCLES_HDR=" + written, flush=True)


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    main(argv)
