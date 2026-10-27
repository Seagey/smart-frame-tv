"""Choosing today's photo from the folder, and getting it ready for a 4K screen.

How it picks (photos.pick in config.json):
  day     a new photo each day, working through the folder in name order (the default)
  rotate  the next photo every time a picture is made (useful with every_hours)
  random  any photo, but never the same one twice in a row
  fixed   always photos.file

Date photos: a file whose name starts with a month and day, like "12-25 tree.jpg", is shown on
that day every year, and is left out on every other day.
"""
import os
import random
import re
from datetime import date

from PIL import Image, ImageOps, ImageStat

try:   # iPhone photos (.heic) work when pillow-heif is installed
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIC = True
except ImportError:
    HEIC = False

W, H = 3840, 2160
EXT = (".jpg", ".jpeg", ".png", ".webp") + ((".heic", ".heif") if HEIC else ())
DATED = re.compile(r"^(\d{2})-(\d{2})[ _-]")
FOCUS = {
    "centre": (0.5, 0.5), "center": (0.5, 0.5), "top": (0.5, 0.2), "bottom": (0.5, 0.8),
    "left": (0.2, 0.5), "right": (0.8, 0.5),
}


class PhotoError(Exception):
    pass


def list_photos(folder):
    if not os.path.isdir(folder):
        raise PhotoError("the photo folder %s does not exist" % folder)
    names = sorted(f for f in os.listdir(folder) if f.lower().endswith(EXT) and not f.startswith("."))
    if not names:
        raise PhotoError("no photos in %s (add .jpg, .png or .webp files%s)" % (folder, ", or .heic" if HEIC else ""))
    return names


def choose(cfg, state, today=None):
    """Return the file name of today's photo, and update the state's rotation index."""
    p = cfg["photos"]
    folder = cfg.photo_folder
    today = today or cfg.now().date()
    names = list_photos(folder)
    if p["pick"] == "fixed":
        if p["file"] not in names:
            raise PhotoError('photos.file "%s" is not in %s' % (p["file"], folder))
        return p["file"]
    stamp = "%02d-%02d" % (today.month, today.day)
    dated = [n for n in names if DATED.match(n)]
    for n in dated:
        if n[:5] == stamp:
            return n
    pool = [n for n in names if n not in dated] or names
    if p["pick"] == "day":
        return pool[(today - date(2000, 1, 1)).days % len(pool)]
    if p["pick"] == "rotate":
        i = (int(state.data.get("photo_index", -1)) + 1) % len(pool)
        state.data["photo_index"] = i
        return pool[i]
    last = state.data.get("last_photo")
    options = [n for n in pool if n != last] or pool
    return random.choice(options)


def prepare(path, out_path, focus="centre"):
    """Open a photo, turn it the right way up, crop it to 16:9 and size it to 3840x2160.

    Saves a clean JPEG without any of the original's metadata (no GPS, no camera details).
    Returns the prepared image.
    """
    try:
        im = Image.open(path)
        im = ImageOps.exif_transpose(im).convert("RGB")
    except Exception as e:
        raise PhotoError("could not open %s: %s" % (os.path.basename(path), e))
    fx, fy = FOCUS.get(focus, FOCUS["centre"])
    scale = max(W / im.width, H / im.height)
    nw, nh = max(W, round(im.width * scale)), max(H, round(im.height * scale))
    im = im.resize((nw, nh), Image.LANCZOS)
    x, y = round((nw - W) * fx), round((nh - H) * fy)
    im = im.crop((x, y, x + W, y + H))
    im.save(out_path, "JPEG", quality=92)
    return im


def ink_for(im, box):
    """Pick dark or light writing for the part of the photo the words sit on.

    box is (left, top, right, bottom) as fractions of the picture.
    """
    l, t, r, b = box
    region = im.crop((int(l * im.width), int(t * im.height), int(r * im.width), int(b * im.height))).convert("L")
    return "dark" if ImageStat.Stat(region).mean[0] > 140 else "light"
