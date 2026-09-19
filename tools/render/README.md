# Photorealistic interior renders

Ray-traced interior views of the villa, rendered with POV-Ray from the same
room layout and furniture the 2D drawings are generated from — so the render
and the drawings cannot describe different buildings.

This is a real ray tracer: global illumination (radiosity), area lights with
soft shadows, reflections, refraction-free glazing, and procedural materials.
It is **not** a photograph. Furniture is parametric — a sofa is a rounded
solid, not an upholstered mesh — so the output reads as a clean architectural
visualisation of simple forms rather than a product photo.

## Requirements

POV-Ray is not a Python package and is not in `requirements.txt`:

```bash
sudo apt-get install -y povray        # Debian/Ubuntu
```

Geometry extraction drives the live web UI, so it also needs Playwright and a
Chromium build (`pip install playwright && playwright install chromium`).

## Use

```bash
python3 -m app.cli serve &                      # the UI must be running
python3 tools/render/extract_geometry.py        # -> villa_geom.json
python3 tools/render/render.py --out-dir renders
```

`extract_geometry.py` fills the Project tab, then reads `villaRooms()`,
`villaFurnitureSolids()` and `slabThickness()` straight out of the page. Edit
`FIELDS` in that file to render a different plot.

`scene.py` turns that JSON into POV-Ray source: walls at full height with door
and window voids subtracted by CSG, glazing, skirting, furniture solids,
curtains, cushions, planting and light fittings.

## Notes on the lighting setup

- Window openings carry **portal area lights**. Without them a radiosity
  sample either sees the bright sky through a window or does not, which is the
  high-variance case radiosity handles worst, and the walls come out blotchy
  at any sample count.
- Wall runs from adjacent rooms are **merged into single spans** before they
  reach POV-Ray. Two rooms sharing a wall each emit a segment on the same
  plane, and a short one can sit entirely inside a long one; left separate,
  the two coincident surfaces make POV-Ray pick one per ray and the whole wall
  speckles. No amount of lighting tuning fixes that — it is geometry.
- `jitter` is off on the area lights, and there are no emissive ceiling
  panels; both add sampling noise for very little.

## Cost

About 3-5 minutes per view at 1400x900 on 4 cores, most of it the radiosity
pretrace. Resolution scales the trace time roughly linearly in pixel count.
