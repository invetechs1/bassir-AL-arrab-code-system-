"""Alarrab standard component library.

A practice keeps one catalogue of components. The same entry drives the tag on
the plan, the row in the furniture schedule and the model in the render, so a
drawing and a visual cannot disagree about what is in the room.

Every entry carries a code, a bilingual name, nominal dimensions in millimetres
and a specification note. `build` returns POV-Ray geometry as a list of
(geometry, texture) pairs, sized to the space it is placed in rather than to a
fixed model, so one family covers a range of rooms.

Dimensions are metres inside build(); the catalogue quotes millimetres the way
a schedule does.
"""

# ----------------------------------------------------------------- geometry
def bx(x, y, w, d, z0, z1):
    return (f"box {{ <{x:.4f},{z0:.4f},{y:.4f}>, "
            f"<{x + w:.4f},{z1:.4f},{y + d:.4f}> }}")


def rb(x, y, w, d, z0, z1, r=0.05):
    """Rounded box via superellipsoid — upholstery, cushions, mattresses."""
    cx, cy, cz = x + w / 2, (z0 + z1) / 2, y + d / 2
    sx = max(w / 2, 0.015); sy = max((z1 - z0) / 2, 0.015); sz = max(d / 2, 0.015)
    e = min(0.42, max(0.10, r / max(sx, sy, sz)))
    return (f"superellipsoid {{ <{e:.3f},{e:.3f}> scale <{sx:.4f},{sy:.4f},{sz:.4f}> "
            f"translate <{cx:.4f},{cy:.4f},{cz:.4f}> }}")


def cyl(cx, cy, z0, z1, r):
    if abs(z1 - z0) < 1e-4 or r <= 0:
        return ""
    return (f"cylinder {{ <{cx:.4f},{z0:.4f},{cy:.4f}>, "
            f"<{cx:.4f},{z1:.4f},{cy:.4f}>, {r:.4f} }}")


def cyl_h(x0, x1, y, z, r, axis="x"):
    """Horizontal cylinder — rails, handles, curtain poles.

    A zero-length cylinder is degenerate and POV-Ray warns and drops it, so
    collapse it to nothing rather than emitting it.
    """
    if abs(x1 - x0) < 1e-4 or r <= 0:
        return ""
    if axis == "x":
        return f"cylinder {{ <{x0:.4f},{z:.4f},{y:.4f}>, <{x1:.4f},{z:.4f},{y:.4f}>, {r:.4f} }}"
    return f"cylinder {{ <{y:.4f},{z:.4f},{x0:.4f}>, <{y:.4f},{z:.4f},{x1:.4f}>, {r:.4f} }}"


def sph(cx, cy, cz, r, sx=1.0, sy=1.0, sz=1.0):
    return (f"sphere {{ <0,0,0>, {r:.4f} scale <{sx:.3f},{sy:.3f},{sz:.3f}> "
            f"translate <{cx:.4f},{cz:.4f},{cy:.4f}> }}")


def tapered_leg(cx, cy, top, sec_top, sec_bot, tex="M_Wood"):
    """A leg that narrows toward the floor. Straight prisms read as blocking."""
    return [(f"cone {{ <{cx:.4f},0,{cy:.4f}>, {sec_bot/2:.4f}, "
             f"<{cx:.4f},{top:.4f},{cy:.4f}>, {sec_top/2:.4f} }}", tex)]


def legs4(x, y, w, d, top, sec=0.05, inset=0.055, tex="M_Wood", taper=0.7):
    out = []
    for lx in (x + inset, x + w - inset):
        for ly in (y + inset, y + d - inset):
            out += tapered_leg(lx, ly, top, sec, sec * taper, tex)
    return out


def panel_door(x, y, w, d, z0, z1, side, tex="M_Lacquer", handle="M_Metal",
               reveal=0.008, inset=0.018):
    """A door leaf set behind a shadow reveal, with a bar handle."""
    out = []
    if side in ("n", "s"):
        yy = y if side == "n" else y + d - inset
        out.append((bx(x + reveal, yy, w - 2 * reveal, inset, z0 + reveal, z1 - reveal), tex))
        hx = x + w / 2 - 0.06
        hz = z1 - 0.12 if (z1 - z0) > 0.7 else (z0 + z1) / 2
        out.append((bx(hx, yy - 0.020 if side == "n" else yy + inset, 0.12, 0.020,
                       hz - 0.012, hz + 0.012), handle))
    else:
        xx = x if side == "w" else x + w - inset
        out.append((bx(xx, y + reveal, inset, d - 2 * reveal, z0 + reveal, z1 - reveal), tex))
        hy = y + d / 2 - 0.06
        hz = z1 - 0.12 if (z1 - z0) > 0.7 else (z0 + z1) / 2
        out.append((bx(xx - 0.020 if side == "w" else xx + inset, hy, 0.020, 0.12,
                       hz - 0.012, hz + 0.012), handle))
    return out


def facing_side(x, y, w, d, toward):
    """Which face of a footprint looks at `toward`."""
    cx, cy = x + w / 2, y + d / 2
    tx, ty = toward
    if abs(tx - cx) > abs(ty - cy):
        return "e" if tx > cx else "w"
    return "s" if ty > cy else "n"


# ------------------------------------------------------------------ seating
def sofa(x, y, w, d, face="n", seats=None):
    """Upholstered sofa: plinth on legs, rolled arms, seat and back cushions.

    `face` is the side the sitter looks out of.
    """
    out, arm, back = [], 0.20, 0.17
    seat_h, top = 0.42, 0.72
    swap = face in ("w", "e")
    if swap:
        x, y, w, d = y, x, d, w      # work in a canonical frame, swap back later

    out.append((rb(x + 0.02, y + 0.02, w - 0.04, d - 0.04, 0.12, seat_h - 0.06, 0.03), "M_Fabric"))
    out += legs4(x, y, w, d, 0.13, 0.045, 0.07, "M_WoodDark", 0.65)

    back_y = y + d - back if face == "n" else y
    out.append((rb(back_y * 0 + x + arm, back_y, w - 2 * arm, back, 0.12, top, 0.05), "M_Fabric"))
    for ax in (x, x + w - arm):                                   # rolled arms
        out.append((rb(ax, y + 0.02, arm, d - 0.04, 0.12, top - 0.14, 0.07), "M_Fabric"))
        out.append((cyl_h(ax + 0.03, ax + arm - 0.03, y + d / 2, top - 0.14, 0.085, "z"), "M_Fabric"))

    inner_d = d - back - 0.04
    n = seats or max(1, int(round((w - 2 * arm) / 0.66)))
    for i in range(n):
        f0, f1 = i / n, (i + 1) / n
        cx0 = x + arm + (w - 2 * arm) * f0 + 0.012
        cx1 = x + arm + (w - 2 * arm) * f1 - 0.012
        cy = y + 0.04 if face == "n" else y + back + 0.02
        out.append((rb(cx0, cy, cx1 - cx0, inner_d, seat_h - 0.06, seat_h + 0.10, 0.055), "M_Fabric"))
        # back cushion, standing slightly proud of the frame
        by = y + d - back - 0.10 if face == "n" else y + back - 0.06
        out.append((rb(cx0 + 0.01, by, cx1 - cx0 - 0.02, 0.15, seat_h + 0.08, top - 0.03, 0.06),
                    "M_FabricAlt"))
    if swap:
        out = [(_swap_xz(g), t) for g, t in out]
    return out


def _swap_xz(geo):
    """Mirror a canonical-frame piece onto the other axis."""
    return f"object {{ {geo} matrix <0,0,1, 0,1,0, 1,0,0, 0,0,0> }}"


def armchair(x, y, w, d, face="n"):
    out, arm = [], 0.15
    seat_h, top = 0.42, 0.74
    out.append((rb(x + 0.02, y + 0.02, w - 0.04, d - 0.04, 0.12, seat_h - 0.05, 0.03), "M_FabricAlt"))
    out += legs4(x, y, w, d, 0.13, 0.04, 0.06, "M_WoodDark", 0.65)
    by = y + d - 0.15 if face == "n" else y
    out.append((rb(x + arm, by, w - 2 * arm, 0.15, 0.12, top, 0.05), "M_FabricAlt"))
    for ax in (x, x + w - arm):
        out.append((rb(ax, y + 0.02, arm, d - 0.04, 0.12, top - 0.16, 0.06), "M_FabricAlt"))
    cy = y + 0.04 if face == "n" else y + 0.17
    out.append((rb(x + arm, cy, w - 2 * arm, d - 0.21, seat_h - 0.05, seat_h + 0.09, 0.05), "M_FabricAlt"))
    return out


def majlis_bench(x, y, w, d, wall="n"):
    """Traditional perimeter seating: low base, seat cushions, back bolsters."""
    out = []
    base_h, seat_h = 0.12, 0.42
    out.append((bx(x, y, w, d, 0, base_h), "M_WoodDark"))
    out.append((bx(x + 0.02, y + 0.02, w - 0.04, d - 0.04, base_h, base_h + 0.02), "M_Wood"))
    horiz = w >= d
    run = w if horiz else d
    n = max(1, int(round(run / 0.62)))
    for i in range(n):
        f0, f1 = i / n, (i + 1) / n
        if horiz:
            a, b = x + w * f0 + 0.010, x + w * f1 - 0.010
            out.append((rb(a, y + 0.03, b - a, d - 0.06, base_h + 0.02, seat_h + 0.04, 0.05), "M_Majlis"))
            by = y + d - 0.17 if wall == "s" else y + 0.02
            out.append((rb(a + 0.01, by, b - a - 0.02, 0.16, seat_h + 0.04, seat_h + 0.44, 0.07),
                        "M_MajlisAlt"))
            out.append((cyl_h(a + 0.06, b - 0.06, by + 0.09, seat_h + 0.14, 0.075, "x"), "M_MajlisAlt"))
        else:
            a, b = y + d * f0 + 0.010, y + d * f1 - 0.010
            out.append((rb(x + 0.03, a, w - 0.06, b - a, base_h + 0.02, seat_h + 0.04, 0.05), "M_Majlis"))
            bxx = x + w - 0.17 if wall == "e" else x + 0.02
            out.append((rb(bxx, a + 0.01, 0.16, b - a - 0.02, seat_h + 0.04, seat_h + 0.44, 0.07),
                        "M_MajlisAlt"))
            out.append((cyl_h(a + 0.06, b - 0.06, bxx + 0.09, seat_h + 0.14, 0.075, "z"), "M_MajlisAlt"))
    return out


# ------------------------------------------------------- tables and storage
def dining_table(x, y, w, d, h=0.75):
    top, apron = 0.038, 0.075
    out = [(bx(x, y, w, d, h - top, h), "M_Wood")]
    out.append((bx(x + 0.09, y + 0.09, w - 0.18, d - 0.18, h - top - apron, h - top), "M_Wood"))
    out += legs4(x, y, w, d, h - top - apron, 0.062, 0.10, "M_Wood", 0.6)
    return out


def dining_chair(x, y, w, d, toward=None):
    """Shaped seat on tapered legs with a slatted back turned away from `toward`."""
    seat_h, out = 0.45, []
    back = facing_side(x, y, w, d, toward) if toward else "n"
    back = {"n": "s", "s": "n", "e": "w", "w": "e"}[back]   # back on the far face
    out += legs4(x, y, w, d, seat_h, 0.035, 0.042, "M_Wood", 0.55)
    out.append((rb(x, y, w, d, seat_h - 0.035, seat_h + 0.012, 0.018), "M_Wood"))
    out.append((rb(x + 0.02, y + 0.02, w - 0.04, d - 0.04, seat_h + 0.012, seat_h + 0.05, 0.02),
                "M_FabricAlt"))
    top = seat_h + 0.50
    if back in ("n", "s"):
        yy = y + 0.012 if back == "n" else y + d - 0.048
        for sx in (x + 0.018, x + w - 0.054):
            out.append((bx(sx, yy, 0.036, 0.036, seat_h, top), "M_Wood"))
        for lv in (0.62, 0.80, 0.98):
            z = seat_h + (top - seat_h) * lv
            out.append((bx(x + 0.018, yy + 0.006, w - 0.036, 0.024, z - 0.030, z + 0.030), "M_Wood"))
    else:
        xx = x + 0.012 if back == "w" else x + w - 0.048
        for sy in (y + 0.018, y + d - 0.054):
            out.append((bx(xx, sy, 0.036, 0.036, seat_h, top), "M_Wood"))
        for lv in (0.62, 0.80, 0.98):
            z = seat_h + (top - seat_h) * lv
            out.append((bx(xx + 0.006, y + 0.018, 0.024, d - 0.036, z - 0.030, z + 0.030), "M_Wood"))
    return out


def coffee_table(x, y, w, d, h=0.40):
    top = 0.035
    out = [(rb(x, y, w, d, h - top, h, 0.012), "M_Wood")]
    out.append((bx(x + 0.10, y + 0.08, w - 0.20, d - 0.16, 0.14, 0.166), "M_Wood"))   # shelf
    out += legs4(x, y, w, d, h - top, 0.055, 0.085, "M_WoodDark", 0.62)
    return out


def carcass(x, y, w, d, h, face="n", doors=None, drawers=0, plinth=0.075,
            tex="M_Wood", cornice=False):
    """Generic cabinet: plinth, carcass, door leaves or drawer fronts, handles."""
    out = [(bx(x, y, w, d, plinth, h), tex)]
    if plinth:
        out.append((bx(x + 0.035, y + 0.035, w - 0.07, d - 0.07, 0, plinth), "M_Shadow"))
    if cornice:
        out.append((bx(x - 0.012, y - 0.012, w + 0.024, d + 0.024, h, h + 0.045), tex))
    horiz = face in ("n", "s")
    span = w if horiz else d
    if drawers:
        for i in range(drawers):
            z0 = plinth + (h - plinth) * i / drawers + 0.008
            z1 = plinth + (h - plinth) * (i + 1) / drawers - 0.008
            out += panel_door(x, y, w, d, z0, z1, face, "M_Lacquer")
        return out
    n = doors or max(1, int(round(span / 0.55)))
    for i in range(n):
        f0, f1 = i / n, (i + 1) / n
        if horiz:
            out += panel_door(x + w * f0, y, w * (f1 - f0), d, plinth + 0.010, h - 0.010, face)
        else:
            out += panel_door(x, y + d * f0, w, d * (f1 - f0), plinth + 0.010, h - 0.010, face)
    return out


def wardrobe(x, y, w, d, h=2.0, face="n"):
    return carcass(x, y, w, d, h, face, doors=max(2, int(round(w / 0.6))),
                   plinth=0.085, tex="M_Wood", cornice=True)


def bedside(x, y, w, d, h=0.5, face="n"):
    return carcass(x, y, w, d, h, face, drawers=2, plinth=0.055, tex="M_Wood")


def tv_unit(x, y, w, d, h=0.5, face="n"):
    out = carcass(x, y, w, d, h, face, doors=max(2, int(round(w / 0.7))),
                  plinth=0.05, tex="M_WoodDark")
    sw = min(1.30, w * 0.80)
    out.append((bx(x + (w - sw) / 2, y + d / 2 - 0.018, sw, 0.036, h + 0.10, h + 0.80), "M_Screen"))
    out.append((bx(x + w / 2 - 0.10, y + d / 2 - 0.028, 0.20, 0.056, h + 0.02, h + 0.10), "M_WoodDark"))
    return out


def console(x, y, w, d, h=0.85):
    out = [(bx(x, y, w, d, h - 0.035, h), "M_Wood")]
    out += legs4(x, y, w, d, h - 0.035, 0.045, 0.07, "M_WoodDark", 0.55)
    out.append((bx(x + 0.07, y + 0.06, w - 0.14, d - 0.12, h * 0.45, h * 0.45 + 0.026), "M_Wood"))
    return out


def desk(x, y, w, d, h=0.75):
    out = [(bx(x, y, w, d, h - 0.035, h), "M_Wood")]
    out += legs4(x, y, w, d, h - 0.035, 0.05, 0.075, "M_Metal", 0.85)
    out.append((bx(x + w * 0.55, y + 0.05, w * 0.40, d - 0.10, h - 0.40, h - 0.045), "M_Wood"))
    return out


# ------------------------------------------------------------------ bedroom
def bed(x, y, w, d, head="n", double=True, hb_max=1.10):
    """Upholstered headboard, base, mattress, duvet with a turned fold, pillows."""
    out, base_h, matt = [], 0.28, 0.52
    out.append((bx(x + 0.05, y + 0.05, w - 0.10, d - 0.10, 0.06, base_h), "M_WoodDark"))
    out += legs4(x + 0.05, y + 0.05, w - 0.10, d - 0.10, 0.07, 0.05, 0.06, "M_Metal", 0.9)
    out.append((rb(x, y, w, d, base_h, matt, 0.045), "M_Mattress"))

    hb_t, hb_h = 0.085, hb_max
    if head in ("n", "s"):
        hy = y - hb_t if head == "n" else y + d
        out.append((rb(x - 0.05, hy, w + 0.10, hb_t, 0.10, hb_h, 0.05), "M_FabricAlt"))
        for i in range(3):                                   # buttoned panel divisions
            px = x + w * (i + 1) / 4
            out.append((cyl_h(hy + 0.004, hy + hb_t - 0.004, px, hb_h * 0.62, 0.011, "z"), "M_FabricAlt"))
    else:
        hx = x - hb_t if head == "w" else x + w
        out.append((rb(hx, y - 0.05, hb_t, d + 0.10, 0.10, hb_h, 0.05), "M_FabricAlt"))

    # duvet: a slab over the lower two-thirds with the top edge turned back
    if head in ("n", "s"):
        dy = y + d * 0.28 if head == "n" else y
        out.append((rb(x - 0.035, dy, w + 0.07, d * 0.72, matt - 0.02, matt + 0.115, 0.05), "M_Duvet"))
        out.append((rb(x - 0.035, dy if head == "n" else dy + d * 0.72 - 0.17,
                       w + 0.07, 0.17, matt + 0.03, matt + 0.145, 0.045), "M_DuvetFold"))
        pw = (w - 0.16) / (2 if double else 1)
        for i in range(2 if double else 1):
            px = x + 0.055 + i * (pw + 0.05)
            py = y + 0.055 if head == "n" else y + d - 0.055 - d * 0.16
            out.append((rb(px, py, pw, d * 0.16, matt, matt + 0.135, 0.06), "M_Pillow"))
    return out


# ------------------------------------------------------------------ kitchen
def base_units(x, y, w, d, face="n", h=0.90):
    """Base cabinets under a stone worktop with an upstand at the wall."""
    out = carcass(x, y, w, d, h - 0.04, face, plinth=0.10, tex="M_Carcass")
    out.append((bx(x - 0.015, y - 0.02, w + 0.03, d + 0.04, h - 0.04, h), "M_Stone"))
    if face in ("n", "s"):
        uy = y + d - 0.02 if face == "n" else y
        out.append((bx(x, uy, w, 0.02, h, h + 0.055), "M_Stone"))
    else:
        ux = x + w - 0.02 if face == "w" else x
        out.append((bx(ux, y, 0.02, d, h, h + 0.055), "M_Stone"))
    return out


def wall_units(x, y, w, d, face="n", sill=1.50, h=0.72):
    out = carcass(x, y, w, d, sill + h, face, plinth=0, tex="M_Carcass")
    # cut the carcass off at the sill by drawing only the upper box
    out = [(bx(x, y, w, d, sill, sill + h), "M_Carcass")]
    n = max(1, int(round((w if face in ("n", "s") else d) / 0.50)))
    for i in range(n):
        f0, f1 = i / n, (i + 1) / n
        if face in ("n", "s"):
            out += panel_door(x + w * f0, y, w * (f1 - f0), d, sill + 0.010, sill + h - 0.010, face)
        else:
            out += panel_door(x, y + d * f0, w, d * (f1 - f0), sill + 0.010, sill + h - 0.010, face)
    out.append((bx(x - 0.01, y - 0.01, w + 0.02, d + 0.02, sill + h, sill + h + 0.035), "M_Carcass"))
    return out


def splashback(x, y, w, d, face="n", z0=0.955, z1=1.50):
    if face in ("n", "s"):
        yy = y + d - 0.012 if face == "n" else y
        return [(bx(x, yy, w, 0.012, z0, z1), "M_Splash")]
    xx = x + w - 0.012 if face == "w" else x
    return [(bx(xx, y, 0.012, d, z0, z1), "M_Splash")]


def sink(cx, cy, top=0.90, w=0.56, d=0.42):
    out = [(bx(cx - w / 2, cy - d / 2, w, d, top - 0.008, top + 0.004), "M_Steel")]
    out.append((bx(cx - w / 2 + 0.03, cy - d / 2 + 0.03, w - 0.06, d - 0.06, top - 0.17, top - 0.008),
                "M_Steel"))
    ty = cy - d / 2 - 0.09
    out.append((cyl(cx, ty, top, top + 0.30, 0.017), "M_Steel"))                      # tap riser
    # spout reaching back over the bowl; a zero-length cylinder is degenerate
    out.append((f"cylinder {{ <{cx:.4f},{top + 0.295:.4f},{ty:.4f}>, "
                f"<{cx:.4f},{top + 0.295:.4f},{ty + 0.20:.4f}>, 0.016 }}", "M_Steel"))
    return out


def hob(cx, cy, top=0.905, w=0.60, d=0.52):
    out = [(bx(cx - w / 2, cy - d / 2, w, d, top, top + 0.012), "M_Glass")]
    for ox in (-0.145, 0.145):
        for oy in (-0.115, 0.115):
            out.append((cyl(cx + ox, cy + oy, top + 0.012, top + 0.022, 0.072), "M_Steel"))
    return out


def fridge(x, y, w, d, h=1.80, face="n"):
    out = [(bx(x, y, w, d, 0.02, h), "M_Appliance")]
    split = h * 0.62
    for z0, z1 in ((0.04, split - 0.008), (split + 0.008, h - 0.02)):
        out += panel_door(x, y, w, d, z0, z1, face, "M_Appliance", "M_Steel", 0.006, 0.022)
    return out


# ------------------------------------------------- sanitary and accessories
def wc_pan(x, y, w, d, face="n"):
    cx, cy = x + w / 2, y + d / 2
    out = [(bx(cx - 0.18, y, 0.36, 0.14, 0.20, 0.82), "M_Sanitary")]                  # cistern
    out.append((rb(cx - 0.175, y + 0.13, 0.35, max(0.30, d - 0.16), 0.10, 0.40, 0.12), "M_Sanitary"))
    out.append((rb(cx - 0.185, y + 0.15, 0.37, max(0.28, d - 0.20), 0.40, 0.425, 0.13), "M_Seat"))
    out.append((bx(cx - 0.09, y + 0.02, 0.18, 0.10, 0.10, 0.22), "M_Sanitary"))
    return out


def basin(x, y, w, d, top=0.85):
    cx, cy = x + w / 2, y + d / 2
    out = [(bx(x, y, w, d, top - 0.04, top), "M_Stone")]                              # vanity top
    out.append((carcass(x, y, w, d, top - 0.04, "s", doors=2, plinth=0.06, tex="M_Wood")[0]))
    out += carcass(x, y, w, d, top - 0.04, "s", doors=2, plinth=0.06, tex="M_Wood")[1:]
    out.append((sph(cx, cy, top + 0.035, 0.19, 1.15, 0.55, 1.0), "M_Sanitary"))       # basin bowl
    out.append((cyl(cx, y + 0.09, top, top + 0.22, 0.016), "M_Steel"))
    out.append((bx(cx - 0.014, y + 0.09, 0.028, 0.15, top + 0.205, top + 0.233), "M_Steel"))
    return out


def shower(x, y, w, d):
    out = [(bx(x, y, w, d, 0, 0.06), "M_Sanitary")]
    out.append((cyl(x + w / 2, y + d / 2, 0.012, 0.028, 0.045), "M_Steel"))           # drain
    out.append((bx(x, y + d - 0.012, w, 0.012, 0.06, 2.00), "M_Glass"))               # screen
    out.append((bx(x + w - 0.012, y, 0.012, d, 0.06, 2.00), "M_Glass"))
    out.append((cyl(x + 0.16, y + 0.16, 1.95, 2.10, 0.016), "M_Steel"))
    out.append((sph(x + 0.16, y + 0.16, 1.93, 0.075, 1, 0.35, 1), "M_Steel"))
    return out


def rug(x, y, w, d):
    return [(bx(x, y, w, d, 0.002, 0.018), "M_Rug"),
            (bx(x + 0.09, y + 0.09, w - 0.18, d - 0.18, 0.018, 0.0195), "M_RugField")]


def planter(cx, cy, r=0.22):
    out = [(f"cone {{ <{cx:.3f},0,{cy:.3f}>, {r*0.78:.3f}, <{cx:.3f},{0.36:.3f},{cy:.3f}>, {r:.3f} }}",
            "M_Pot")]
    out.append((cyl(cx, cy, 0.36, 0.52, 0.035), "M_Stem"))
    for ox, oy, rr, hh, zz in ((0, 0, 0.44, 0.52, 0.86), (0.20, 0.13, 0.33, 0.40, 0.70),
                               (-0.17, -0.12, 0.29, 0.34, 0.62), (0.05, -0.20, 0.26, 0.30, 0.95)):
        out.append((sph(cx + ox, cy + oy, zz, rr, 1.0, hh / (2 * rr), 1.0), "M_Foliage"))
    return out


def pendant(cx, cy, ceil, drop=0.80, r=0.20):
    out = [(cyl(cx, cy, ceil - drop, ceil, 0.009), "M_Cord")]
    out.append((f"cone {{ <{cx:.3f},{ceil-drop:.3f},{cy:.3f}>, 0.055, "
                f"<{cx:.3f},{ceil-drop-0.26:.3f},{cy:.3f}>, {r:.3f} open }}", "M_Shade"))
    out.append((sph(cx, cy, ceil - drop - 0.245, 0.055), "M_Bulb"))
    return out


def curtain(x, y, w, d, height, pole=True):
    """A pinch-pleated panel; the waves normal supplies the fold."""
    out = [(bx(x, y, w, d, 0.02, height), "M_Curtain")]
    if pole:
        if w >= d:
            out.append((cyl_h(x - 0.08, x + w + 0.08, y + d / 2, height + 0.06, 0.016, "x"), "M_Metal"))
        else:
            out.append((cyl_h(y - 0.08, y + d + 0.08, x + w / 2, height + 0.06, 0.016, "z"), "M_Metal"))
    return out


def artwork(x, y, w, d, z0=1.20, z1=2.00):
    return [(bx(x, y, w, d, z0, z1), "M_Frame"),
            (bx(x + 0.035 if w > d else x, y + 0.035 if d > w else y,
                w - (0.07 if w > d else 0), d - (0.07 if d > w else 0),
                z0 + 0.035, z1 - 0.035), "M_Art")]


# ---------------------------------------------------------------- catalogue
# code -> (name_ar, name_en, nominal W x D x H in mm, specification note)
CATALOGUE = {
    "SOF-301": ("كنبة ٣ مقاعد", "Three-seat sofa", "2400x900x720", "Upholstered, timber frame, fabric grade 3"),
    "ARM-101": ("كرسي مفرد", "Armchair", "750x780x740", "Upholstered, timber legs"),
    "MAJ-201": ("جلسة مجلس عربي", "Arabic majlis seating", "run x 800x420", "Fixed base, loose seat and back cushions"),
    "TBL-401": ("طاولة وسط", "Coffee table", "1100x550x400", "Solid timber top, lower shelf"),
    "TBL-501": ("طاولة طعام", "Dining table", "1000x700x750", "Solid timber, apron frame"),
    "CHR-501": ("كرسي طعام", "Dining chair", "450x450x950", "Timber frame, upholstered seat pad"),
    "BED-601": ("سرير مزدوج", "Double bed", "1800x2000x1100", "Upholstered headboard, slatted base"),
    "BED-602": ("سرير مفرد", "Single bed", "1200x2000x1100", "Upholstered headboard, slatted base"),
    "NIG-603": ("كومودينو", "Bedside cabinet", "450x450x500", "Two drawers, soft close"),
    "WRD-604": ("دولاب ملابس", "Wardrobe", "2000x600x2000", "Hinged doors, internal hanging and shelving"),
    "TVU-402": ("وحدة تلفزيون", "TV unit", "1800x420x500", "Cabinet with cable management"),
    "CON-403": ("كونسول مدخل", "Entry console", "1100x360x850", "Timber, single shelf"),
    "DSK-605": ("مكتب دراسة", "Study desk", "1000x550x750", "Timber top, metal legs"),
    "KIT-701": ("قواعد مطبخ", "Kitchen base units", "run x 620x900", "Carcass with lacquered fronts, stone worktop"),
    "KIT-702": ("وحدات علوية", "Kitchen wall units", "run x 350x720", "Lacquered fronts, sill at 1500"),
    "KIT-703": ("ظهر مطبخ", "Splashback", "run x 12x545", "Full-height ceramic behind work zones"),
    "SNK-704": ("حوض جلي ومخلط", "Sink and mixer", "560x420", "Stainless steel, single bowl"),
    "HOB-705": ("موقد غاز", "Gas hob", "600x520", "Four burner, glass plate"),
    "FRG-706": ("ثلاجة", "Refrigerator", "620x700x1800", "Two door, freestanding"),
    "WCP-801": ("مرحاض", "WC pan and cistern", "370x600x820", "Close coupled, dual flush"),
    "BAS-802": ("مغسلة وخزانة", "Basin and vanity", "600x450x850", "Counter basin on vanity unit"),
    "SHW-803": ("دش وقاطع زجاجي", "Shower and screen", "900x900x2000", "Tray with glazed screen"),
    "RUG-901": ("سجادة", "Rug", "per layout", "Hand tufted, low pile"),
    "PLT-902": ("نبات داخلي بحوض", "Planter", "440x440x1400", "Live plant, ceramic pot"),
    "LGT-903": ("مدلاة", "Pendant light", "400 dia", "Metal shade, warm 3000K lamp"),
    "CUR-904": ("ستارة", "Curtain panel", "per opening", "Pinch pleat on metal pole"),
    "ART-905": ("لوحة فنية", "Artwork", "1100x800", "Framed print"),
}


def spec(code):
    """Catalogue row for a code, for schedules and reports."""
    row = CATALOGUE.get(code)
    if not row:
        return None
    ar, en, dims, note = row
    return {"code": code, "name_ar": ar, "name_en": en, "nominal_mm": dims, "specification": note}


# ---------------------------------------------------------------- materials
MATERIALS = """
#declare M_Wood = texture {
  pigment { wood turbulence 0.10 scale <1.40,1.40,3.2>
    color_map { [0.00 rgb <0.455,0.320,0.196>][0.45 rgb <0.545,0.396,0.248>]
                [0.72 rgb <0.400,0.272,0.166>][1.00 rgb <0.505,0.360,0.222>] } }
  finish { diffuse 0.52 specular 0.30 roughness 0.010
           reflection { 0.020 } conserve_energy ambient 0 }
}
#declare M_WoodDark = texture {
  pigment { wood turbulence 0.12 scale <1.20,1.20,3.0>
    color_map { [0.00 rgb <0.235,0.158,0.100>][0.50 rgb <0.300,0.206,0.134>]
                [1.00 rgb <0.198,0.132,0.086>] } }
  finish { diffuse 0.42 specular 0.32 roughness 0.008
           reflection { 0.024 } conserve_energy ambient 0 }
}
#declare M_Fabric = texture {
  pigment { rgb <0.560,0.552,0.524> }
  normal { bumps 0.34 scale 0.0075 }
  finish { diffuse 0.70 specular 0.045 roughness 0.42 ambient 0 }
}
#declare M_FabricAlt = texture {
  pigment { rgb <0.492,0.494,0.476> }
  normal { bumps 0.30 scale 0.008 }
  finish { diffuse 0.70 specular 0.05 roughness 0.40 ambient 0 }
}
#declare M_Majlis = texture {
  pigment { rgb <0.352,0.430,0.392> }
  normal { bumps 0.36 scale 0.0075 }
  finish { diffuse 0.66 specular 0.05 roughness 0.40 ambient 0 }
}
#declare M_MajlisAlt = texture {
  pigment { rgb <0.300,0.372,0.340> }
  normal { bumps 0.38 scale 0.0070 }
  finish { diffuse 0.64 specular 0.05 roughness 0.40 ambient 0 }
}
#declare M_Lacquer = texture {
  pigment { rgb <0.905,0.898,0.882> }
  finish { diffuse 0.48 specular 0.45 roughness 0.0045
           reflection { 0.045 } conserve_energy ambient 0 }
}
#declare M_Carcass = texture {
  pigment { rgb <0.855,0.848,0.836> }
  finish { diffuse 0.58 specular 0.20 roughness 0.02 ambient 0 }
}
#declare M_Metal = texture {
  pigment { rgb <0.585,0.595,0.610> }
  finish { diffuse 0.22 specular 0.80 roughness 0.010 metallic
           reflection { 0.30 metallic } conserve_energy ambient 0 }
}
#declare M_Steel = texture {
  pigment { rgb <0.700,0.710,0.722> }
  finish { diffuse 0.18 specular 0.90 roughness 0.006 metallic
           reflection { 0.42 metallic } conserve_energy ambient 0 }
}
#declare M_Shadow = texture { pigment { rgb <0.140,0.140,0.138> } finish { diffuse 0.18 ambient 0 } }
#declare M_Stone = texture {
  pigment { granite scale 0.10
    color_map { [0 rgb <0.660,0.655,0.642>][0.5 rgb <0.800,0.794,0.780>][1 rgb <0.575,0.572,0.564>] } }
  finish { diffuse 0.50 specular 0.42 roughness 0.0040
           reflection { 0.045 } conserve_energy ambient 0 }
}
#declare M_Splash = texture {
  pigment { rgb <0.900,0.896,0.884> }
  finish { diffuse 0.42 specular 0.55 roughness 0.0025
           reflection { 0.060 } conserve_energy ambient 0 }
}
#declare M_Screen = texture {
  pigment { rgb <0.055,0.058,0.062> }
  finish { diffuse 0.10 specular 0.60 roughness 0.003
           reflection { 0.070 } conserve_energy ambient 0 }
}
#declare M_Appliance = texture {
  pigment { rgb <0.812,0.818,0.826> }
  finish { diffuse 0.36 specular 0.55 roughness 0.006
           reflection { 0.075 } conserve_energy ambient 0 }
}
#declare M_Sanitary = texture {
  pigment { rgb <0.968,0.970,0.968> }
  finish { diffuse 0.52 specular 0.60 roughness 0.0022
           reflection { 0.055 } conserve_energy ambient 0 }
}
#declare M_Seat = texture {
  pigment { rgb <0.945,0.948,0.946> }
  finish { diffuse 0.50 specular 0.45 roughness 0.004 ambient 0 }
}
#declare M_Mattress = texture {
  pigment { rgb <0.935,0.932,0.922> }
  normal { bumps 0.14 scale 0.05 }
  finish { diffuse 0.74 specular 0.04 roughness 0.4 ambient 0 }
}
#declare M_Duvet = texture {
  pigment { rgb <0.890,0.886,0.872> }
  normal { bumps 0.22 scale 0.11 }
  finish { diffuse 0.74 specular 0.04 roughness 0.42 ambient 0 }
}
#declare M_DuvetFold = texture {
  pigment { rgb <0.945,0.942,0.930> }
  normal { bumps 0.18 scale 0.08 }
  finish { diffuse 0.76 specular 0.05 roughness 0.40 ambient 0 }
}
#declare M_Pillow = texture {
  pigment { rgb <0.962,0.960,0.952> }
  normal { bumps 0.26 scale 0.045 }
  finish { diffuse 0.76 specular 0.05 roughness 0.36 ambient 0 }
}
#declare M_Rug = texture {
  pigment { rgb <0.352,0.352,0.336> }
  normal { bumps 0.7 scale 0.006 }
  finish { diffuse 0.72 specular 0.015 roughness 0.55 ambient 0 }
}
#declare M_RugField = texture {
  pigment { rgb <0.300,0.362,0.336> }
  normal { bumps 0.8 scale 0.005 }
  finish { diffuse 0.72 specular 0.015 roughness 0.55 ambient 0 }
}
#declare M_Pot = texture {
  pigment { rgb <0.722,0.692,0.640> }
  finish { diffuse 0.52 specular 0.30 roughness 0.010
           reflection { 0.025 } conserve_energy ambient 0 }
}
#declare M_Stem = texture { pigment { rgb <0.315,0.288,0.205> } finish { diffuse 0.6 ambient 0 } }
#declare M_Foliage = texture {
  pigment { bozo scale 0.09
    color_map { [0 rgb <0.180,0.286,0.170>][0.5 rgb <0.245,0.358,0.216>][1 rgb <0.152,0.245,0.148>] } }
  normal { bumps 0.55 scale 0.04 }
  finish { diffuse 0.60 specular 0.14 roughness 0.05 ambient 0 }
}
#declare M_Cord = texture { pigment { rgb <0.10,0.10,0.10> } finish { diffuse 0.35 ambient 0 } }
#declare M_Shade = texture {
  pigment { rgb <0.930,0.922,0.905> }
  finish { diffuse 0.55 specular 0.30 roughness 0.012 ambient 0 }
}
#declare M_Bulb = texture {
  pigment { rgb <1,0.96,0.90> } finish { ambient 2.2 diffuse 0 }
}
#declare M_Curtain = texture {
  pigment { rgb <0.888,0.872,0.834> }
  normal { waves 0.30 frequency 11 scale 0.26 }
  finish { diffuse 0.74 specular 0.035 roughness 0.45 ambient 0 }
}
#declare M_Frame = texture { pigment { rgb <0.155,0.150,0.145> } finish { diffuse 0.35 specular 0.2 ambient 0 } }
#declare M_Art = texture {
  pigment { marble turbulence 0.62 scale 0.42
    color_map { [0 rgb <0.790,0.752,0.690>][0.45 rgb <0.508,0.545,0.522>][1 rgb <0.320,0.372,0.392>] } }
  finish { diffuse 0.58 specular 0.06 ambient 0 }
}
#declare M_Glass = texture {
  pigment { rgbf <1,1,1,0.965> }
  finish { diffuse 0.0 specular 0.40 roughness 0.001
           reflection { 0.035 } conserve_energy ambient 0 }
}
"""
