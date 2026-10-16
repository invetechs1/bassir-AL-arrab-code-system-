"""Parse the subset of POV-Ray solids the component library emits.

The library is the single source of truth for what a piece of furniture is,
and it speaks POV-Ray. Rather than maintain a second description of every
sofa and wardrobe for a second renderer, read back what the library already
produced and hand the shapes to whoever wants them.

Only the forms `library.py` and `scene.py` actually emit are handled: box,
cylinder, cone, sphere, superellipsoid, and the CSG wrappers union, merge and
difference, with the scale/translate suffixes the helpers attach and the
bare flags (`open` on a lampshade cone, `hollow`, `no_shadow`). Anything
else raises, so a new primitive cannot slip through as silence.

POV-Ray is y-up; the result keeps those coordinates, and the caller maps axes.
"""
import re

NUM = r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?"
VEC = re.compile(rf"<\s*({NUM})\s*,\s*({NUM})\s*,\s*({NUM})\s*>")
VEC2 = re.compile(rf"<\s*({NUM})\s*,\s*({NUM})\s*>")


class ParseError(ValueError):
    pass


def _tokens(src):
    """Split into braces, identifiers, vectors and numbers."""
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c.isspace():
            i += 1
        elif c in "{}":
            out.append((c, c)); i += 1
        elif c == "<":
            j = src.index(">", i) + 1
            out.append(("vec", src[i:j])); i = j
        elif c == ",":
            i += 1
        elif c.isalpha() or c == "_":
            j = i
            while j < n and (src[j].isalnum() or src[j] == "_"):
                j += 1
            out.append(("id", src[i:j])); i = j
        else:
            m = re.match(NUM, src[i:])
            if not m:
                raise ParseError(f"unexpected {src[i:i+24]!r}")
            out.append(("num", m.group(0))); i += m.end()
    return out


def _vec3(text):
    m = VEC.search(text)
    if not m:
        raise ParseError(f"not a 3-vector: {text!r}")
    return tuple(float(g) for g in m.groups())


def parse(src):
    """Return a list of shape dicts, each with its accumulated transform."""
    toks = _tokens(src)
    pos = [0]

    def peek():
        return toks[pos[0]] if pos[0] < len(toks) else (None, None)

    def take():
        t = toks[pos[0]]; pos[0] += 1; return t

    BARE = ("open", "hollow", "no_shadow")      # flags that take no argument

    def modifiers(node):
        """scale / translate / rotate suffixes, and bare flags like `open`."""
        while True:
            kind, val = peek()
            if kind == "id" and val in BARE:
                take()
                node[val] = True
                continue
            if kind == "id" and val in ("scale", "translate", "rotate"):
                take()
                k2, v2 = take()
                if k2 == "vec":
                    node.setdefault(val, []).append(_vec3(v2))
                elif k2 == "num":                      # uniform scale
                    f = float(v2)
                    node.setdefault(val, []).append((f, f, f))
                else:
                    raise ParseError(f"{val} wants a vector, got {v2!r}")
            else:
                return node

    def block():
        kind, val = take()
        if kind != "id":
            raise ParseError(f"expected a shape name, got {val!r}")
        if take()[0] != "{":
            raise ParseError(f"{val} without a brace")
        node = {"type": val}

        if val == "box":
            node["lo"] = _vec3(take()[1]); node["hi"] = _vec3(take()[1])
        elif val == "cylinder":
            node["a"] = _vec3(take()[1]); node["b"] = _vec3(take()[1])
            node["r"] = float(take()[1])
        elif val == "cone":
            node["a"] = _vec3(take()[1]); node["ra"] = float(take()[1])
            node["b"] = _vec3(take()[1]); node["rb"] = float(take()[1])
        elif val == "sphere":
            node["c"] = _vec3(take()[1]); node["r"] = float(take()[1])
        elif val == "superellipsoid":
            m = VEC2.search(take()[1])
            node["e"] = (float(m.group(1)), float(m.group(2)))
        elif val in ("union", "merge", "difference"):
            kids = []
            while peek()[0] != "}":
                kids.append(block())
            node["children"] = kids
        else:
            raise ParseError(f"unsupported primitive {val!r}")

        modifiers(node)
        if take()[0] != "}":
            raise ParseError(f"{val} not closed")
        return node

    shapes = []
    while pos[0] < len(toks):
        shapes.append(block())
    return shapes
