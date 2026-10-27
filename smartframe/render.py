"""Making the picture: 3840x2160, the photo plus the day's details in the chosen style.

The main way is headless Chrome (or Chromium, Edge, Brave): it lays the words out like a
well set web page, with proper kerning and real fonts, which is what makes the label look printed
rather than stamped on. If no Chrome is found, or it fails, a plainer Pillow version is made
instead, so the TV still gets a picture that day.
"""
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import photos

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "fonts")
TEMPLATE = os.path.join(HERE, "templates", "picture.html")
W, H = 3840, 2160

FONT_FACES = [
    ("Cormorant Garamond", "normal", 500, "CormorantGaramond-Medium.ttf"),
    ("Cormorant Garamond", "normal", 600, "CormorantGaramond-SemiBold.ttf"),
    ("Cormorant Garamond", "italic", 500, "CormorantGaramond-MediumItalic.ttf"),
    ("Jost", "normal", 400, "Jost-Regular.ttf"),
    ("Jost", "normal", 500, "Jost-Medium.ttf"),
]
FOCUS_CSS = {"centre": "50% 50%", "center": "50% 50%", "top": "50% 20%", "bottom": "50% 80%",
             "left": "20% 50%", "right": "80% 50%"}
# Where the words sit, as fractions of the picture, for choosing dark or light writing.
INK_BOX = {"top-left": (0.03, 0.04, 0.5, 0.42), "top-right": (0.5, 0.04, 0.97, 0.42),
           "bottom-left": (0.03, 0.58, 0.5, 0.96), "bottom-right": (0.5, 0.58, 0.97, 0.96)}

CHROME_PATHS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]
CHROME_NAMES = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "brave-browser"]


def find_chrome(cfg=None):
    want = (cfg.get("chrome") if cfg else None) or os.environ.get("SMARTFRAME_CHROME")
    if want:
        return want if os.path.exists(want) else shutil.which(want)
    for p in CHROME_PATHS:
        if os.path.exists(p):
            return p
    for n in CHROME_NAMES:
        p = shutil.which(n)
        if p:
            return p
    return None


def _font_css():
    rules = []
    for family, style, weight, file in FONT_FACES:
        with open(os.path.join(FONTS, file), "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        rules.append('@font-face { font-family: "%s"; font-style: %s; font-weight: %d; font-display: block; '
                     'src: url(data:font/ttf;base64,%s) format("truetype"); }' % (family, style, weight, b64))
    return "\n".join(rules)


def _ink(cfg, im):
    if cfg["ink"] != "auto":
        return cfg["ink"]
    if cfg["style"] in ("gallery", "postcard"):
        return "dark"
    return photos.ink_for(im, INK_BOX[cfg["position"]])


def render(cfg, photo_path, info, out_path, engine="auto"):
    """Make the picture and save it as a JPEG (or PNG if out_path ends in .png). Returns the engine used."""
    with tempfile.TemporaryDirectory(prefix="smartframe-") as tmp:
        im = photos.prepare(photo_path, os.path.join(tmp, "photo.jpg"), cfg["photos"].get("focus", "centre"))
        data = {"style": cfg["style"], "position": cfg["position"], "ink": _ink(cfg, im), "mat": cfg["mat"],
                "focus": FOCUS_CSS.get(cfg["photos"].get("focus", "centre"), "50% 50%"), "info": info}
        chrome = find_chrome(cfg) if engine in ("auto", "chrome") else None
        if engine == "chrome" and not chrome:
            raise RuntimeError("Chrome was not found (install Google Chrome or Chromium, or set \"chrome\" in config.json)")
        if chrome:
            try:
                _chrome(cfg, chrome, tmp, data, out_path)
                return "chrome"
            except Exception as e:
                if engine == "chrome":
                    raise
                print("render: Chrome did not work (%s), making the plain version instead" % e)
        _pillow(im, data, out_path)
        return "pillow"


def _chrome(cfg, chrome, tmp, data, out_path):
    with open(TEMPLATE, encoding="utf-8") as f:
        page = f.read()
    page = page.replace("/*FONTS*/", _font_css()).replace("/*DATA*/{}", json.dumps(data).replace("</", "<\\/"))
    html = os.path.join(tmp, "picture.html")
    with open(html, "w", encoding="utf-8") as f:
        f.write(page)
    png = os.path.join(tmp, "shot.png")
    profile = os.path.join(tmp, "chrome-profile")   # its own each time, so two renders never collide
    args = [chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
            "--no-default-browser-check", "--disable-extensions", "--mute-audio",
            "--window-size=1920,1080", "--force-device-scale-factor=2", "--virtual-time-budget=6000",
            "--user-data-dir=" + profile, "--screenshot=" + png, "file://" + html.replace("\\", "/")]
    if sys.platform.startswith("linux") and hasattr(os, "geteuid") and os.geteuid() == 0:
        args.insert(1, "--no-sandbox")   # Chromium refuses to start as root without it
    r = subprocess.run(args, capture_output=True, timeout=120)
    if not os.path.exists(png):
        raise RuntimeError("no screenshot (exit %s): %s" % (r.returncode, r.stderr.decode(errors="replace")[-300:].strip()))
    im = Image.open(png).convert("RGB")
    if im.size != (W, H):
        im = im.resize((W, H), Image.LANCZOS) if abs(im.width / im.height - W / H) < 0.01 else None
        if im is None:
            raise RuntimeError("the screenshot came out the wrong shape")
    _save(im, out_path)


def _save(im, out_path):
    if out_path.lower().endswith(".png"):
        im.save(out_path, "PNG")
    else:
        im.save(out_path, "JPEG", quality=90)


# ---------------------------------------------------------------- the plain Pillow version

def _font(name, size):
    return ImageFont.truetype(os.path.join(FONTS, name), size)


def _lines(info):
    """The details as (kind, text) lines, in the order the blocks are listed."""
    out = []
    for b in info["blocks"]:
        if b == "date" and info.get("date"):
            out.append(("date", info["date"]))
        elif b == "weather" and info.get("weather"):
            out.append(("text", info["weather"]))
        elif b == "calendar":
            evs = info["events"] or ([{"when": "", "title": info["empty_text"]}] if info.get("empty_text") else [])
            for e in evs:
                out.append(("text", ("%s  %s" % (e["when"], e["title"])).strip()))
        elif b == "reminders":
            for r in info["reminders"]:
                out.append(("text", r["text"]))
        elif b == "quote" and info.get("quote"):
            out.append(("quote", info["quote"]))
    return out


def _pillow(im, data, out_path):
    s = data["style"]
    lines = _lines(data["info"])
    if s in ("gallery", "postcard"):
        mat = data.get("mat") or "#f4f2ee"
        canvas = Image.new("RGB", (W, H), mat)
        pw, ph = 3240, 1822
        canvas.paste(im.resize((pw, ph), Image.LANCZOS), (300, 144))
        d = ImageDraw.Draw(canvas)
        x, y = 300, 2064
        f_date, f_text, f_quote = _font("CormorantGaramond-SemiBold.ttf", 68), _font("Jost-Regular.ttf", 42), _font("CormorantGaramond-MediumItalic.ttf", 52)
        for kind, text in lines:
            f = f_date if kind == "date" else f_quote if kind == "quote" else f_text
            colour = "#2c2a27" if kind != "text" else "#75706a"
            d.text((x, y), text, font=f, fill=colour, anchor="ls")
            x += d.textlength(text, font=f) + 70
            if x > 3500:
                break
        _save(canvas, out_path)
        return
    canvas = im.copy()
    dark = data["ink"] == "dark"
    ink, halo = ("#22323a", (236, 242, 244)) if dark else ("#fbfaf7", (10, 16, 24))
    big = 128 if s == "sky" else 40
    f_date = _font("CormorantGaramond-SemiBold.ttf" if s == "sky" else "Jost-Medium.ttf", big)
    f_text = _font("Jost-Medium.ttf" if s == "sky" else "Jost-Regular.ttf", 56 if s == "sky" else 40)
    f_quote = _font("CormorantGaramond-MediumItalic.ttf", 64 if s == "sky" else 50)
    step = {"date": big + 40, "text": 84 if s == "sky" else 66, "quote": 90 if s == "sky" else 70}
    right, bottom = data["position"].endswith("right"), data["position"].startswith("bottom")
    margin = 184 if s == "sky" else 144
    total = sum(step[k] for k, _ in lines)
    y = (H - margin - total + big) if bottom else margin + big
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d, g = ImageDraw.Draw(layer), ImageDraw.Draw(glow)
    for kind, text in lines:
        f = f_date if kind == "date" else f_quote if kind == "quote" else f_text
        if s == "minimal" and kind == "date":
            text = text.upper()
        x = W - margin if right else margin
        anchor = "rs" if right else "ls"
        g.text((x, y), text, font=f, fill=halo + (200,), anchor=anchor)
        d.text((x, y), text, font=f, fill=ink, anchor=anchor)
        y += step[kind]
    glow = glow.filter(ImageFilter.GaussianBlur(18))
    out = Image.alpha_composite(Image.alpha_composite(canvas.convert("RGBA"), glow), layer).convert("RGB")
    _save(out, out_path)
