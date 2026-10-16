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

## Second renderer: Blender / Cycles

`blender_render.py` renders the same villa through Cycles. It does not
duplicate the model: it reads back the solids `library.py` already emitted,
through `povparse.py`, so a sofa cannot differ between the two renderers.

```bash
VILLA_GEOM=villa.json blender -b --python tools/render/blender_render.py -- \
    --view majlis-ground --out majlis.png --width 1920 --height 1200 --samples 600
```

It writes a linear Radiance `.hdr` and stops. Grading is the same
`post.grade` the POV-Ray path uses, so the two images differ only by the
renderer:

```bash
python -c "import post; post.grade('majlis.hdr','majlis.png',use_denoise=True)"
```

What Cycles brings that POV-Ray 3.7 cannot: a Principled BSDF (GGX
microfacet, real roughness/metallic/IOR), the Nishita physical sun-and-sky
model in place of a hand-written gradient, and Open Image Denoise.

Three things cost real time to find, and are worth knowing before changing
this file:

- **Refractive caustics must stay on.** Daylight reaches an interior by
  refracting through a pane and then bouncing off a diffuse surface, which
  Cycles classifies as a caustic. Switching caustics off - normal practice
  for exteriors - makes the room render pure black while the windows still
  look bright. The median of the frame was exactly zero until this was fixed.
- **Window portals need their normals facing in.** Backwards portals are not
  an error, they simply do nothing.
- **The file cannot be called `cycles.py`.** Blender ships a `cycles` addon
  module, and that name wins for anything that imports it.

Denoising is optional (`pip install pyoidn`). Distribution builds of Blender
are frequently compiled without OpenImageDenoise - this is why the denoise
step lives in `post.py` rather than in Cycles' own settings.
