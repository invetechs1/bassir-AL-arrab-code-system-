"""Ray-trace interior views of the villa with POV-Ray.

    sudo apt-get install -y povray
    python3 tools/render/extract_geometry.py
    python3 tools/render/render.py --out-dir renders
"""
import argparse, os, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

VIEWS = [
    ("majlis-ground",   "ground", "majlis",  dict(eye=(0.93, 0.93), target=(0.25, 0.15), angle=66)),
    ("living-ground",   "ground", "living",  dict(eye=(0.15, 0.10), target=(0.80, 0.93), angle=66)),
    ("kitchen-ground",  "ground", "kitchen", dict(eye=(0.92, 0.17), target=(0.28, 0.88), angle=70)),
    ("master-first",    "first",  "master",  dict(eye=(0.14, 0.90), target=(0.83, 0.12), angle=64)),
    ("bedroom2-first",  "first",  "bed2",    dict(eye=(0.87, 0.90), target=(0.18, 0.12), angle=62)),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="renders")
    ap.add_argument("--width", type=int, default=1400)
    ap.add_argument("--height", type=int, default=900)
    ap.add_argument("--only", default=None, help="render a single view by name")
    ap.add_argument("--exposure", type=float, default=0.26,
                    help="tone-mapping exposure applied to the HDR")
    args = ap.parse_args()

    import scene, post
    os.makedirs(args.out_dir, exist_ok=True)
    for name, level, room, cam in VIEWS:
        if args.only and args.only != name:
            continue
        pov = os.path.join(args.out_dir, f"{name}.pov")
        hdr = os.path.join(args.out_dir, f"{name}.hdr")
        png = os.path.join(args.out_dir, f"render-{name}.png")
        scene.emit(level, scene.camera_for(level, room, **cam), pov)
        t0 = time.time()
        # render linear HDR, then tone map: clipping to 8 bit in the renderer
        # throws away every highlight the grade needs
        r = subprocess.run(["povray", f"+I{pov}", f"+O{hdr}",
                            f"+W{args.width}", f"+H{args.height}",
                            "+A0.3", "-D", "+Q9", "+AM2", "+R2", "+FH"],
                           capture_output=True, text=True)
        if r.returncode:
            print(f"{name}: FAILED in {time.time() - t0:.0f}s", flush=True)
            print(r.stderr[-800:], file=sys.stderr)
            continue
        post.grade(hdr, png, exposure=args.exposure, temp=1.03, bloom_strength=0.09,
                   grain_amount=0.0026, vig=0.24, contrast=1.14, ca=0.30)
        print(f"{name}: ok in {time.time() - t0:.0f}s -> {png}", flush=True)


if __name__ == "__main__":
    main()
