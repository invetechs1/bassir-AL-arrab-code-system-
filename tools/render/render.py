"""Ray-trace interior views of the villa with POV-Ray.

    sudo apt-get install -y povray
    python3 tools/render/extract_geometry.py
    python3 tools/render/render.py --out-dir renders
"""
import argparse, os, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

VIEWS = [
    ("majlis-ground",   "ground", "majlis",  dict(eye=(0.93, 0.93), target=(0.25, 0.15), angle=66)),
    ("living-ground",   "ground", "living",  dict(eye=(0.50, 0.07), target=(0.50, 0.96), angle=64)),
    ("kitchen-ground",  "ground", "kitchen", dict(eye=(0.92, 0.17), target=(0.28, 0.88), angle=70)),
    ("master-first",    "first",  "master",  dict(eye=(0.50, 0.94), target=(0.50, 0.08), angle=66)),
    ("bedroom2-first",  "first",  "bed2",    dict(eye=(0.50, 0.92), target=(0.50, 0.10), angle=64)),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="renders")
    ap.add_argument("--width", type=int, default=1400)
    ap.add_argument("--height", type=int, default=900)
    ap.add_argument("--only", default=None, help="render a single view by name")
    args = ap.parse_args()

    import scene
    os.makedirs(args.out_dir, exist_ok=True)
    for name, level, room, cam in VIEWS:
        if args.only and args.only != name:
            continue
        pov = os.path.join(args.out_dir, f"{name}.pov")
        png = os.path.join(args.out_dir, f"render-{name}.png")
        scene.emit(level, scene.camera_for(level, room, **cam), pov)
        t0 = time.time()
        r = subprocess.run(["povray", f"+I{pov}", f"+O{png}",
                            f"+W{args.width}", f"+H{args.height}",
                            "+A0.3", "-D", "+Q9", "+AM2", "+R2"],
                           capture_output=True, text=True)
        ok = "ok" if r.returncode == 0 else "FAILED"
        print(f"{name}: {ok} in {time.time() - t0:.0f}s", flush=True)
        if r.returncode:
            print(r.stderr[-800:], file=sys.stderr)


if __name__ == "__main__":
    main()
