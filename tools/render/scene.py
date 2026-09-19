"""Build a POV-Ray scene from the villa geometry the drawings are generated from.

Plan coords are (x right, y depth) with z up; POV-Ray is y-up, so plan (x, y)
maps to POV (x, _, y) and heights go to POV y.
"""
import json, math, os, sys

GEOM_PATH = os.environ.get("VILLA_GEOM", "villa_geom.json")
G = json.load(open(GEOM_PATH))
W, D = G["W"], G["D"]
WALL_EXT, WALL_INT, DOOR_W = G["wallExt"], G["wallInt"], G["doorW"]
CEIL = 2.90                 # clear height
DOOR_H, SILL, WIN_H = 2.10, 0.90, 1.45

# ---------------------------------------------------------------- materials
TEX = {
 "floor":   "T_Floor", "wall": "T_Wall", "part": "T_Wall",
 "seat":    "T_FabricGreen", "soft": "T_FabricGrey", "wood": "T_Wood",
 "counter": "T_Stone", "white": "T_White", "green": "T_Rug", "step": "T_Stone",
}
SOFT = {"seat", "soft"}     # rounded, upholstered

def edge_rect(r, side, at, length):
    """Opening rect on a room edge -> (x, y, horiz)."""
    if side == "n":  return (r["x"] + r["w"] * at - length / 2, r["y"], True)
    if side == "s":  return (r["x"] + r["w"] * at - length / 2, r["y"] + r["h"], True)
    if side == "w":  return (r["x"], r["y"] + r["h"] * at - length / 2, False)
    return (r["x"] + r["w"], r["y"] + r["h"] * at - length / 2, False)

def wall_runs(level):
    runs = [(0, 0, W, WALL_EXT), (0, D - WALL_EXT, W, WALL_EXT),
            (0, 0, WALL_EXT, D), (W - WALL_EXT, 0, WALL_EXT, D)]
    t = WALL_INT
    horiz, vert = {}, {}
    for r in G[level]["rooms"]:
        if r["y"] > 0.01:
            horiz.setdefault(round(r["y"] - t / 2, 3), []).append((r["x"], r["x"] + r["w"]))
        if r["y"] + r["h"] < D - 0.01:
            horiz.setdefault(round(r["y"] + r["h"] - t / 2, 3), []).append((r["x"], r["x"] + r["w"]))
        if r["x"] > 0.01:
            vert.setdefault(round(r["x"] - t / 2, 3), []).append((r["y"], r["y"] + r["h"]))
        if r["x"] + r["w"] < W - 0.01:
            vert.setdefault(round(r["x"] + r["w"] - t / 2, 3), []).append((r["y"], r["y"] + r["h"]))

    def merge_spans(spans):
        """Collapse overlapping intervals into one run.

        Two rooms sharing a wall each emit a segment on the same plane, and a
        short one can sit entirely inside a long one. Left as separate boxes
        those give POV-Ray two coincident surfaces and it picks one per ray,
        which shows up as speckle across the whole wall.
        """
        out = []
        for a, b in sorted(spans):
            if out and a <= out[-1][1] + 1e-6:
                out[-1][1] = max(out[-1][1], b)
            else:
                out.append([a, b])
        return out

    for y, spans in horiz.items():
        for a, b in merge_spans(spans):
            runs.append((a, y, b - a, t))
    for x, spans in vert.items():
        for a, b in merge_spans(spans):
            runs.append((x, a, t, b - a))
    return runs

def openings(level):
    """Door and window voids to subtract from the wall system."""
    out = []
    for r in G[level]["rooms"]:
        if r.get("door"):
            d = r["door"]
            x, y, horiz = edge_rect(r, d["side"], d["at"], DOOR_W)
            out.append((x - (0 if horiz else 0.3), y - (0.3 if horiz else 0),
                        DOOR_W if horiz else 0.6, 0.6 if horiz else DOOR_W, 0.0, DOOR_H))
        for w in r.get("win", []):
            x, y, horiz = edge_rect(r, w["side"], w["at"], w["len"])
            on_edge = ((w["side"] == "n" and y < 0.01) or (w["side"] == "s" and abs(y - D) < 0.01) or
                       (w["side"] == "w" and x < 0.01) or (w["side"] == "e" and abs(x - W) < 0.01))
            if not on_edge:
                continue
            out.append((x - (0 if horiz else 0.4), y - (0.4 if horiz else 0),
                        w["len"] if horiz else 0.8, 0.8 if horiz else w["len"], SILL, SILL + WIN_H))
    return out

def glass(level):
    panes = []
    for r in G[level]["rooms"]:
        for w in r.get("win", []):
            x, y, horiz = edge_rect(r, w["side"], w["at"], w["len"])
            on_edge = ((w["side"] == "n" and y < 0.01) or (w["side"] == "s" and abs(y - D) < 0.01) or
                       (w["side"] == "w" and x < 0.01) or (w["side"] == "e" and abs(x - W) < 0.01))
            if not on_edge:
                continue
            if horiz:
                panes.append((x, y - 0.012, w["len"], 0.024, SILL, SILL + WIN_H, w["side"]))
            else:
                panes.append((x - 0.012, y, 0.024, w["len"], SILL, SILL + WIN_H, w["side"]))
    return panes

def box(x, y, w, d, z0, z1):
    return f"box {{ <{x:.3f},{z0:.3f},{y:.3f}>, <{x+w:.3f},{z1:.3f},{y+d:.3f}> }}"

def rbox(x, y, w, d, z0, z1, r=0.06):
    """Rounded box via superellipsoid, for upholstery."""
    cx, cy, cz = x + w / 2, (z0 + z1) / 2, y + d / 2
    sx, sy, sz = max(w / 2, 0.02), max((z1 - z0) / 2, 0.02), max(d / 2, 0.02)
    e = min(0.35, max(0.12, r / max(sx, sy, sz)))
    return (f"superellipsoid {{ <{e:.3f},{e:.3f}> scale <{sx:.3f},{sy:.3f},{sz:.3f}> "
            f"translate <{cx:.3f},{cy:.3f},{cz:.3f}> }}")

# ---------------------------------------------------------------- scene text
HEADER = """#version 3.7;
#include "colors.inc"
#include "textures.inc"

global_settings {
  assumed_gamma 1.0
  max_trace_level 5
  radiosity {
    pretrace_start 0.08 pretrace_end 0.015
    count 300 nearest_count 16 error_bound 0.30
    recursion_limit 2 low_error_factor 0.5
    gray_threshold 0 minimum_reuse 0.008 maximum_reuse 0.05
    brightness 1 adc_bailout 0.02 always_sample off
    normal off media off
    RAD_CACHE
  }
}

#declare T_Floor = texture {
  pigment { rgb <0.845,0.825,0.795> }
  normal { granite 0.012 scale 0.4 }
  finish { diffuse 0.62 specular 0.35 roughness 0.0035
           reflection { 0.030 } conserve_energy ambient 0 }
}
#declare T_Wall = texture {
  pigment { rgb <0.928,0.918,0.900> }
  finish { diffuse 0.80 specular 0.02 roughness 0.2 ambient 0 }
}
#declare T_Ceiling = texture {
  pigment { rgb <0.960,0.955,0.945> }
  finish { diffuse 0.82 specular 0.01 ambient 0 }
}
#declare T_FabricGreen = texture {
  pigment { rgb <0.360,0.440,0.400> }
  normal { bumps 0.35 scale 0.012 }
  finish { diffuse 0.68 specular 0.06 roughness 0.35 ambient 0 }
}
#declare T_FabricGrey = texture {
  pigment { rgb <0.545,0.545,0.520> }
  normal { bumps 0.30 scale 0.012 }
  finish { diffuse 0.70 specular 0.05 roughness 0.35 ambient 0 }
}
#declare T_Wood = texture {
  pigment { wood color_map { [0.0 rgb <0.400,0.268,0.160>][0.55 rgb <0.470,0.325,0.196>]
                             [1.0 rgb <0.345,0.222,0.130>] } turbulence 0.32 scale <0.16,0.16,1.6> }
  finish { diffuse 0.56 specular 0.30 roughness 0.006
           reflection { 0.015 } conserve_energy ambient 0 }
}
#declare T_Stone = texture {
  pigment { granite color_map { [0 rgb <0.70,0.695,0.680>][0.5 rgb <0.795,0.790,0.775>]
                                [1 rgb <0.615,0.615,0.605>] } scale 0.11 }
  finish { diffuse 0.55 specular 0.40 roughness 0.004
           reflection { 0.040 } conserve_energy ambient 0 }
}
#declare T_White = texture {
  pigment { rgb <0.955,0.960,0.958> }
  finish { diffuse 0.60 specular 0.42 roughness 0.0035
           reflection { 0.030 } conserve_energy ambient 0 }
}
#declare T_Rug = texture {
  pigment { rgb <0.300,0.382,0.352> }
  normal { bumps 0.7 scale 0.007 }
  finish { diffuse 0.74 specular 0.02 roughness 0.5 ambient 0 }
}
#declare T_Cushion = texture {
  pigment { rgb <0.735,0.700,0.630> }
  normal { bumps 0.42 scale 0.010 }
  finish { diffuse 0.72 specular 0.05 roughness 0.4 ambient 0 }
}
#declare T_Curtain = texture {
  pigment { rgb <0.885,0.865,0.820> }
  normal { waves 0.22 frequency 8 scale 0.34 }
  finish { diffuse 0.76 specular 0.03 roughness 0.45 ambient 0 }
}
#declare T_Plant = texture {
  pigment { rgb <0.235,0.330,0.215> }
  normal { bumps 0.6 scale 0.05 }
  finish { diffuse 0.62 specular 0.12 roughness 0.08 ambient 0 }
}
#declare T_Art = texture {
  pigment { marble turbulence 0.6 color_map { [0 rgb <0.80,0.76,0.70>][0.5 rgb <0.52,0.55,0.53>]
                                              [1 rgb <0.35,0.40,0.42>] } scale 0.5 }
  finish { diffuse 0.6 specular 0.08 ambient 0 }
}
#declare T_Glass = texture {
  pigment { rgbf <1.0,1.0,1.0,0.992> }
  finish { diffuse 0.0 specular 0.25 roughness 0.001 ambient 0 }
}
#declare I_Glass = interior { ior 1.0 }

// daylight: warm sun plus a bright sky the windows can see
sky_sphere { pigment { gradient y
  color_map { [0.0 rgb <0.74,0.79,0.86>][0.35 rgb <0.58,0.70,0.87>][1.0 rgb <0.34,0.50,0.78>] }
  scale 2 translate -1 } }

light_source { <-14, 16, -20> color rgb <0.72,0.655,0.545>
  area_light <2.6,0,0>, <0,0,2.6>, 7, 7 adaptive 0 circular orient }
// exterior context so the glazing shows a scene rather than flat blue
plane { y, -0.19 texture { pigment { rgb <0.665,0.610,0.520> }
  normal { granite 0.02 scale 0.5 } finish { diffuse 0.6 ambient 0 } } }
#declare T_Far = texture { pigment { rgb <0.78,0.755,0.715> } finish { diffuse 0.68 ambient 0 } };
object { box { <-34,0,-30>, <-16,7.5,-16> } texture { T_Far } }
object { box { <14,0,-27>, <30,5.5,-13> } texture { T_Far } }
object { box { <-30,0,16>, <-14,6.5,30> } texture { T_Far } }
#declare T_Palm = texture { pigment { rgb <0.32,0.38,0.26> } finish { diffuse 0.62 ambient 0 } };
object { cylinder { <-4.5,0,-7>, <-4.5,3.4,-7>, 0.16 } texture { pigment { rgb <0.38,0.31,0.22> } finish { diffuse 0.6 ambient 0 } } }
object { sphere { <-4.5,3.8,-7>, 1.25 scale <1,0.55,1> } texture { T_Palm } }
object { cylinder { <13,0,5>, <13,3.0,5>, 0.15 } texture { pigment { rgb <0.38,0.31,0.22> } finish { diffuse 0.6 ambient 0 } } }
object { sphere { <13,3.35,5>, 1.1 scale <1,0.55,1> } texture { T_Palm } }

light_source { <26, 15, 24> color rgb <0.07,0.08,0.10>
  area_light <3,0,0>, <0,0,3>, 2, 2 adaptive 1 jitter shadowless }
"""

def emit(level, cam, out_path, rad=""):
    rooms = G[level]["rooms"]
    L = [HEADER.replace("RAD_CACHE", rad)]
    L.append(cam)

    # floor slab and ceiling
    L.append(f"object {{ {box(-0.3, -0.3, W + 0.6, D + 0.6, -0.18, 0.0)} texture {{ T_Floor }} }}")
    L.append(f"object {{ {box(-0.3, -0.3, W + 0.6, D + 0.6, CEIL, CEIL + 0.22)} texture {{ T_Ceiling }} }}")

    # wall system with door and window voids cut out
    runs = "\n    ".join(f"object {{ {box(x, y, w, d, 0, CEIL)} }}" for x, y, w, d in wall_runs(level))
    voids = "\n    ".join(f"object {{ {box(x, y, w, d, z0, z1)} }}"
                          for x, y, w, d, z0, z1 in openings(level))
    L.append(f"difference {{\n  merge {{\n    {runs}\n  }}\n  union {{\n    {voids}\n  }}\n"
             f"  texture {{ T_Wall }}\n}}")

    # skirting
    sk = "\n    ".join(f"object {{ {box(x, y, w, d, 0, 0.09)} }}" for x, y, w, d in wall_runs(level))
    L.append(f"difference {{\n  merge {{\n    {sk}\n  }}\n  union {{\n    {voids}\n  }}\n"
             f"  texture {{ T_White }}\n}}")

    # glazing
    for x, y, w, d, z0, z1, side in glass(level):
        L.append(f"object {{ {box(x, y, w, d, z0, z1)} texture {{ T_Glass }} interior {{ I_Glass }} }}")

    # furniture
    for b in G[level]["furn"]:
        tex = TEX.get(b["kind"], "T_Wall")
        z0, z1 = b["z"], b["z"] + b["h"]
        geo = (rbox(b["x"], b["y"], b["w"], b["d"], z0, z1)
               if b["kind"] in SOFT and min(b["w"], b["d"], b["h"]) > 0.12
               else box(b["x"], b["y"], b["w"], b["d"], z0, z1))
        L.append(f"object {{ {geo} texture {{ {tex} }} }}")

    # portal lights sitting in the window openings
    IN0 = {"n": (0, 1), "s": (0, -1), "w": (1, 0), "e": (-1, 0)}
    for x, y, w, d, z0, z1, side in glass(level):
        dx, dy = IN0[side]
        cx, cy = x + w / 2 + dx * 0.10, y + d / 2 + dy * 0.10
        cz = (z0 + z1) / 2
        span = max(w, d)
        if side in ("n", "s"):
            a1, a2 = f"<{span:.2f},0,0>", f"<0,{(z1-z0):.2f},0>"
        else:
            a1, a2 = f"<0,0,{span:.2f}>", f"<0,{(z1-z0):.2f},0>"
        L.append(f"light_source {{ <{cx:.2f},{cz:.2f},{cy:.2f}> color rgb <0.255,0.272,0.310>\n"
                 f"  area_light {a1}, {a2}, 5, 5 adaptive 0 circular orient }}")

    # throw cushions along the back of each seat run
    for b in G[level]["furn"]:
        if b["kind"] != "seat" or b["h"] > 0.55:
            continue
        horiz = b["w"] >= b["d"]
        run = b["w"] if horiz else b["d"]
        n = max(1, int(run // 0.95))
        for i in range(n):
            f = (i + 0.5) / n
            cs = 0.34
            if horiz:
                cxx, czz = b["x"] + b["w"] * f - cs / 2, b["y"] + 0.04
            else:
                cxx, czz = b["x"] + 0.04, b["y"] + b["d"] * f - cs / 2
            L.append(f"object {{ {rbox(cxx, czz, cs, cs*0.42, b['z']+b['h'], b['z']+b['h']+0.26, 0.09)} "
                     f"texture {{ T_Cushion }} }}")

    # curtain panels, pushed clear of the wall into the room
    IN = {"n": (0, 1), "s": (0, -1), "w": (1, 0), "e": (-1, 0)}
    for x, y, w, d, z0, z1, side in glass(level):
        dx, dy = IN[side]
        off = 0.20
        top = SILL + WIN_H + 0.30
        if side in ("n", "s"):
            cy = y + dy * off
            for px in (x - 0.32, x + w + 0.04):
                L.append(f"object {{ {box(px, cy - 0.055, 0.30, 0.11, 0.02, top)} texture {{ T_Curtain }} }}")
        else:
            cx = x + dx * off
            for pz in (y - 0.32, y + d + 0.04):
                L.append(f"object {{ {box(cx - 0.055, pz, 0.11, 0.30, 0.02, top)} texture {{ T_Curtain }} }}")

    # a plant and a piece of wall art, placed only where they actually fit
    def free(bx, by, bw, bd):
        for f in G[level]["furn"]:
            if not (bx >= f["x"] + f["w"] or bx + bw <= f["x"] or
                    by >= f["y"] + f["d"] or by + bd <= f["y"]):
                return False
        return True

    for r in rooms:
        if r["w"] * r["h"] < 12 or r["type"] in ("stair", "wc", "bath", "kitchen"):
            continue
        # plant: try each corner, take the first clear one
        for fx, fy in ((0.08, 0.08), (0.92, 0.08), (0.08, 0.92), (0.92, 0.92)):
            px = r["x"] + r["w"] * fx
            pz = r["y"] + r["h"] * fy
            px = min(max(px, r["x"] + 0.34), r["x"] + r["w"] - 0.34)
            pz = min(max(pz, r["y"] + 0.34), r["y"] + r["h"] - 0.34)
            if not free(px - 0.26, pz - 0.26, 0.52, 0.52):
                continue
            L.append(f"object {{ cylinder {{ <{px:.2f},0,{pz:.2f}>, <{px:.2f},0.34,{pz:.2f}>, 0.20 }} "
                     f"texture {{ pigment {{ rgb <0.70,0.66,0.60> }} finish {{ diffuse 0.6 specular 0.15 ambient 0 }} }} }}")
            for ox_, oy_, rr, hh in ((0, 0, 0.44, 1.05), (0.16, 0.10, 0.34, 0.78), (-0.14, -0.10, 0.30, 0.62)):
                L.append(f"object {{ sphere {{ <{px+ox_:.2f},{0.34+hh*0.55:.2f},{pz+oy_:.2f}>, {rr:.2f} "
                         f"scale <1,{hh/(2*rr):.2f},1> }} texture {{ T_Plant }} }}")
            break

        # art: only on a wall carrying neither a window nor this room's door
        busy = {w["side"] for w in r.get("win", [])}
        if r.get("door"):
            busy.add(r["door"]["side"])
        for side in ("n", "s", "w", "e"):
            if side in busy:
                continue
            if side == "n":   ax, az, aw, ad = r["x"] + r["w"] / 2 - 0.55, r["y"] + 0.06, 1.10, 0.035
            elif side == "s": ax, az, aw, ad = r["x"] + r["w"] / 2 - 0.55, r["y"] + r["h"] - 0.095, 1.10, 0.035
            elif side == "w": ax, az, aw, ad = r["x"] + 0.06, r["y"] + r["h"] / 2 - 0.55, 0.035, 1.10
            else:             ax, az, aw, ad = r["x"] + r["w"] - 0.095, r["y"] + r["h"] / 2 - 0.55, 0.035, 1.10
            L.append(f"object {{ {box(ax, az, aw, ad, 1.25, 2.05)} texture {{ T_Art }} }}")
            break

    # pendant over each coffee / dining table
    for b in G[level]["furn"]:
        if b["kind"] != "wood" or b["h"] > 0.8 or b["w"] < 0.55 or b["d"] < 0.4:
            continue
        cx, cy = b["x"] + b["w"] / 2, b["y"] + b["d"] / 2
        L.append(f"cylinder {{ <{cx:.2f},{CEIL:.2f},{cy:.2f}>, <{cx:.2f},{CEIL-0.55:.2f},{cy:.2f}>, 0.008 "
                 f"texture {{ pigment {{ rgb 0.15 }} finish {{ diffuse 0.4 ambient 0 }} }} }}")
        L.append(f"object {{ cone {{ <{cx:.2f},{CEIL-0.55:.2f},{cy:.2f}>, 0.06, "
                 f"<{cx:.2f},{CEIL-0.80:.2f},{cy:.2f}>, 0.20 open }} "
                 f"texture {{ pigment {{ rgb <0.94,0.92,0.88> }} finish {{ diffuse 0.5 specular 0.3 ambient 0 }} }} }}")
        L.append(f"light_source {{ <{cx:.2f},{CEIL-0.78:.2f},{cy:.2f}> color rgb <0.16,0.147,0.126>\n"
                 f"  area_light <0.22,0,0>, <0,0,0.22>, 5, 5 adaptive 0 circular orient }}")

    # ceiling downlights, one per room
    for r in rooms:
        if r["w"] * r["h"] < 7:
            continue
        cx, cy = r["x"] + r["w"] / 2, r["y"] + r["h"] / 2
        L.append(f"light_source {{ <{cx:.2f},{CEIL-0.12:.2f},{cy:.2f}> color rgb <0.115,0.107,0.094>\n"
                 f"  area_light <0.40,0,0>, <0,0,0.40>, 5, 5 adaptive 0 circular orient }}")
        L.append(f"object {{ {box(cx-0.18, cy-0.18, 0.36, 0.36, CEIL-0.03, CEIL-0.005)} "
                 f"texture {{ pigment {{ rgb <0.97,0.96,0.94> }} finish {{ diffuse 0.3 specular 0.2 ambient 0 }} }} }}")

    open(out_path, "w").write("\n".join(L) + "\n")
    return out_path

def camera_for(level, room_key, eye=(0.88, 0.86), target=(0.30, 0.22),
               h=1.52, th=1.05, angle=62):
    """Camera placed by fractions of the room rect, so framing is deliberate.

    eye/target are (fx, fy) fractions of the room's own rectangle.
    """
    r = next(x for x in G[level]["rooms"] if x["key"] == room_key)
    ex, ez = r["x"] + r["w"] * eye[0], r["y"] + r["h"] * eye[1]
    tx, tz = r["x"] + r["w"] * target[0], r["y"] + r["h"] * target[1]

    def blocked(px, pz):
        """True if the eye sits inside a piece of furniture at eye height."""
        for f in G[level]["furn"]:
            if (f["x"] - 0.22 <= px <= f["x"] + f["w"] + 0.22 and
                    f["y"] - 0.22 <= pz <= f["y"] + f["d"] + 0.22 and
                    f["z"] <= h <= f["z"] + f["h"]):
                return True
        return False

    if blocked(ex, ez):
        # slide along the room edges until the eye is in clear air
        best = None
        for fx in (0.08, 0.2, 0.35, 0.5, 0.65, 0.8, 0.92):
            for fy in (0.92, 0.8, 0.08, 0.2, 0.65, 0.5):
                cx2, cz2 = r["x"] + r["w"] * fx, r["y"] + r["h"] * fy
                if blocked(cx2, cz2):
                    continue
                d2 = (cx2 - tx) ** 2 + (cz2 - tz) ** 2
                if best is None or d2 > best[0]:
                    best = (d2, cx2, cz2)
        if best:
            _, ex, ez = best
        else:
            raise SystemExit(f"no clear camera position in {room_key}")
    return (f"camera {{ perspective location <{ex:.2f},{h},{ez:.2f}> "
            f"look_at <{tx:.2f},{th},{tz:.2f}> angle {angle} }}")
