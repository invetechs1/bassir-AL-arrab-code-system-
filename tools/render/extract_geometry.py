"""Pull the villa geometry out of the running web UI.

The room layout and furniture live in web/app.js so the drawings and the
render describe the same building. Rather than reimplementing that layout in
Python, this drives the live page and dumps what the drawing engine itself
computed.

    python3 -m app.cli serve &
    python3 tools/render/extract_geometry.py --url http://127.0.0.1:8000/ui
"""
import argparse, json

FIELDS = {
    "project_name": "فيلا سكنية 200 م²", "city": "الرياض", "office": "مكتب بصير الهندسي",
    "plot_w": "12.5", "plot_d": "16", "sb_f": "3", "sb_s": "2", "sb_r": "2",
    "floors": "2", "floor_h": "3.2", "units": "1", "parking": "2",
}
SELECTS = {"land_use": "residential", "building_type": "villa"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000/ui")
    ap.add_argument("--out", default="villa_geom.json")
    ap.add_argument("--chromium", default=None, help="explicit browser executable path")
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        kw = {"executable_path": args.chromium} if args.chromium else {}
        b = p.chromium.launch(**kw)
        pg = b.new_page(viewport={"width": 1400, "height": 900})
        pg.goto(args.url, wait_until="networkidle")
        pg.click('[data-tab="project"]')
        pg.wait_for_timeout(300)
        for n, v in SELECTS.items():
            pg.select_option(f'[data-field="{n}"]', v)
        pg.wait_for_timeout(150)
        for n, v in FIELDS.items():
            el = pg.query_selector(f'[data-field="{n}"]')
            if el:
                el.fill(v)
                el.dispatch_event("input")
        pg.wait_for_timeout(350)
        data = pg.evaluate("""() => {
          var g = geom();
          function lvl(n){ return { rooms: villaRooms(n, g.bw, g.bd),
                                    furn: villaFurnitureSolids(n, g.bw, g.bd) }; }
          return { W: g.bw, D: g.bd, fh: g.fh, floors: g.floors, slab: slabThickness(g),
                   wallExt: WALL_EXT, wallInt: WALL_INT, doorW: DOOR_W,
                   ground: lvl("ground"), first: lvl("first") };
        }""")
        b.close()
    json.dump(data, open(args.out, "w"), ensure_ascii=False, indent=1)
    print(f"{args.out}: {data['W']} x {data['D']} m, "
          f"{len(data['ground']['rooms'])} + {len(data['first']['rooms'])} rooms")


if __name__ == "__main__":
    main()
