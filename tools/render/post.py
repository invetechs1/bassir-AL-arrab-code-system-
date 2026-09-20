"""Tone mapping and grade for HDR renders.

POV-Ray writes linear radiance, and values in a daylit interior run well above
1.0. Saving that straight to an 8-bit PNG clips every highlight flat, which is
a large part of why an untreated render reads as CG. This reads the HDR, works
in linear float, and applies the same chain a visualiser would: exposure, a
filmic curve, bloom on the values that were over range, a lens vignette, a
little chromatic aberration and grain, then sRGB encode.
"""
import numpy as np


# ------------------------------------------------------------ Radiance RGBE
def read_hdr(path):
    """Read a Radiance .hdr into a float32 HxWx3 array of linear radiance."""
    with open(path, "rb") as f:
        if not f.readline().startswith(b"#?"):
            raise ValueError("not a Radiance file")
        while True:
            line = f.readline()
            if line.strip() == b"":
                break
        dims = f.readline().decode().split()
        h, w = int(dims[1]), int(dims[3])
        data = np.zeros((h, w, 4), dtype=np.uint8)
        for y in range(h):
            head = f.read(4)
            if len(head) < 4:
                raise ValueError("truncated scanline")
            if head[0] == 2 and head[1] == 2 and (head[2] << 8 | head[3]) == w:
                # adaptive RLE: four separate channel planes
                for c in range(4):
                    x = 0
                    while x < w:
                        n = f.read(1)[0]
                        if n > 128:                       # a run
                            val = f.read(1)[0]
                            data[y, x:x + n - 128, c] = val
                            x += n - 128
                        else:                             # a literal span
                            data[y, x:x + n, c] = np.frombuffer(f.read(n), dtype=np.uint8)
                            x += n
            else:                                          # flat scanline
                rest = f.read(4 * w - 4)
                data[y] = np.frombuffer(head + rest, dtype=np.uint8).reshape(w, 4)

    e = data[:, :, 3].astype(np.int32)
    scale = np.where(e == 0, 0.0, np.ldexp(1.0, e - 136)).astype(np.float32)
    rgb = data[:, :, :3].astype(np.float32) + 0.5
    return rgb * scale[:, :, None]


# ---------------------------------------------------------------- operators
def aces(x):
    """ACES filmic curve — rolls highlights off instead of clipping them."""
    a, b, c, d, e = 2.51, 0.03, 2.43, 0.59, 0.14
    return np.clip((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0)


def _box(a, radius, axis):
    """One box pass along an axis.

    A running sum needs a leading zero so that a window of k = 2r+1 over an
    array padded by r on each side comes back at the original length.
    """
    k = 2 * radius + 1
    pad = [(0, 0)] * a.ndim
    pad[axis] = (radius, radius)
    p = np.pad(a, pad, mode="edge")
    zero = np.zeros_like(np.take(p, [0], axis=axis))
    cs = np.cumsum(np.concatenate([zero, p], axis=axis), axis=axis)
    hi = np.take(cs, range(k, cs.shape[axis]), axis=axis)
    lo = np.take(cs, range(0, cs.shape[axis] - k), axis=axis)
    return (hi - lo) / k


def _blur(img, radius):
    """Separable box blur repeated three times, which approximates a gaussian."""
    if radius < 1:
        return img
    out = img
    for _ in range(3):
        out = _box(out, radius, 0)
        out = _box(out, radius, 1)
    return out


def bloom(lin, threshold=1.0, strength=0.09, radius=None):
    """Light spilling from anything that was over range, as a real lens does."""
    h, w = lin.shape[:2]
    radius = radius or max(3, int(min(h, w) * 0.012))
    over = np.maximum(lin - threshold, 0.0)
    if over.max() <= 0:
        return lin
    return lin + _blur(over, radius) * strength


def vignette(img, amount=0.22):
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    return img * (1.0 - amount * np.clip(r / 1.414, 0, 1) ** 2.2)[:, :, None]


def chromatic(img, px=1.0):
    """Scale the red and blue channels apart very slightly."""
    h, w = img.shape[:2]
    out = img.copy()
    for c, s in ((0, 1.0 + px / w), (2, 1.0 - px / w)):
        ys = np.clip(((np.arange(h) - h / 2) / s + h / 2).astype(np.int32), 0, h - 1)
        xs = np.clip(((np.arange(w) - w / 2) / s + w / 2).astype(np.int32), 0, w - 1)
        out[:, :, c] = img[np.ix_(ys, xs)][:, :, c]
    return out


def grain(img, amount=0.006, seed=7):
    rng = np.random.default_rng(seed)
    n = rng.normal(0.0, amount, img.shape[:2]).astype(np.float32)
    return np.clip(img + n[:, :, None] * (1.0 - img), 0, 1)


def white_balance(lin, temp=1.0):
    """temp > 1 warms the image, < 1 cools it."""
    g = np.array([temp, 1.0, 2.0 - temp], dtype=np.float32)
    return lin * g


def srgb(lin):
    a = 0.055
    return np.where(lin <= 0.0031308, lin * 12.92, (1 + a) * np.power(lin, 1 / 2.4) - a)


def grade(path_in, path_out, exposure=1.0, temp=1.02, bloom_strength=0.09,
          vig=0.26, ca=0.45, grain_amount=0.006, contrast=1.13, lift=0.004):
    from PIL import Image
    lin = read_hdr(path_in) * exposure
    lin = white_balance(lin, temp)
    lin = bloom(lin, 1.0, bloom_strength)
    img = aces(lin)
    img = np.clip((img - 0.5) * contrast + 0.5, 0, 1)
    img = np.clip(img * (1.0 - lift) + lift, 0, 1)   # a touch of film lift in the blacks
    img = vignette(img, vig)
    if ca:
        img = chromatic(img, ca)
    img = grain(img, grain_amount)
    out = (np.clip(srgb(img), 0, 1) * 255.0 + 0.5).astype(np.uint8)
    Image.fromarray(out, "RGB").save(path_out, quality=96)
    return path_out
