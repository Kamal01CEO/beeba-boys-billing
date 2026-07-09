"""Billing Software — prepare the shop logo as a 1-bit thermal-printable bitmap."""
import os

LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "logo.png")
_cache: dict = {}


def get_receipt_logo(width_dots: int = 384, path: str = LOGO_PATH):
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return None
    if not os.path.exists(path):
        return None

    mtime = os.path.getmtime(path)
    key = (path, width_dots)
    cached = _cache.get(key)
    if cached and cached["mtime"] == mtime:
        return cached["img"]

    img = Image.open(path).convert("L")

    # Auto-invert dark-background logos so paper (background) stays white.
    hist = img.histogram()
    pixels = sum(hist) or 1
    mean = sum(i * hist[i] for i in range(256)) / pixels
    if mean < 128:
        img = ImageOps.invert(img)

    w, h = img.size
    new_h = max(1, round(h * (width_dots / w)))
    img = img.resize((width_dots, new_h))
    img = img.convert("1")  # dither to 1-bit

    _cache[key] = {"mtime": mtime, "img": img}
    return img
