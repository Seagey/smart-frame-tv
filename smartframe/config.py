"""Reading config.json, with defaults for everything that is left out.

The settings file lives next to the tool (config.json, git ignores it). Everything the tool saves
for itself (the TV's pairing token, which pictures it uploaded, the last picture) goes in a "data"
folder next to that file, also ignored by git.
"""
import copy
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

STYLES = ("gallery", "sky", "minimal", "postcard")
POSITIONS = ("top-left", "top-right", "bottom-left", "bottom-right")
BLOCKS = ("date", "weather", "calendar", "reminders", "quote")
DAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

DEFAULTS = {
    "frame": {"ip": "", "port": 8002, "name": "SmartFrame"},
    "timezone": "",
    "photos": {"folder": "photos", "pick": "day", "file": "", "focus": "centre"},
    "style": "gallery",
    "position": "top-left",
    "ink": "auto",
    "mat": "#f4f2ee",
    "date_order": "day-month",
    "clock": "12h",
    "blocks": [
        {"type": "date"},
        {"type": "weather"},
        {"type": "calendar"},
        {"type": "reminders"},
    ],
    "place": {"name": "", "latitude": None, "longitude": None},
    "weather": {"units": "celsius", "show_place": False, "rain_chance": False},
    "calendar": {"ics_urls": [], "days": 2, "max": 3, "hide": [], "empty_text": "Nothing planned today"},
    "reminders": [],
    "quote": {"text": "", "lines": []},
    "schedule": {"start_hour": 5, "every_hours": 0},
    "keep_previous": 0,
}


class ConfigError(Exception):
    pass


def _merge(base, extra):
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


class Config:
    def __init__(self, data, path=None):
        self.path = os.path.abspath(path) if path else None
        self.root = os.path.dirname(self.path) if self.path else os.getcwd()
        self.data = _merge(DEFAULTS, data)
        self.validate()

    # ---- where things live ----
    @property
    def data_dir(self):
        d = os.path.join(self.root, "data")
        os.makedirs(d, exist_ok=True)
        return d

    def file(self, name):
        return os.path.join(self.data_dir, name)

    @property
    def photo_folder(self):
        f = os.path.expanduser(self.data["photos"]["folder"])
        return f if os.path.isabs(f) else os.path.join(self.root, f)

    # ---- handy values ----
    def __getitem__(self, key):
        return self.data[key]

    def get(self, key, default=None):
        return self.data.get(key, default)

    @property
    def tz(self):
        name = self.data.get("timezone") or ""
        if name:
            return ZoneInfo(name)
        return datetime.now().astimezone().tzinfo

    def now(self):
        return datetime.now(self.tz)

    def block(self, kind):
        for b in self.data["blocks"]:
            if b.get("type") == kind and b.get("on", True):
                return b
        return None

    def validate(self):
        d = self.data
        if d["style"] not in STYLES:
            raise ConfigError('style must be one of %s, not "%s"' % (", ".join(STYLES), d["style"]))
        if d["position"] not in POSITIONS:
            raise ConfigError('position must be one of %s, not "%s"' % (", ".join(POSITIONS), d["position"]))
        if d["ink"] not in ("auto", "dark", "light"):
            raise ConfigError('ink must be "auto", "dark" or "light"')
        if d["photos"]["pick"] not in ("day", "rotate", "random", "fixed"):
            raise ConfigError('photos.pick must be "day", "rotate", "random" or "fixed"')
        if d["photos"]["pick"] == "fixed" and not d["photos"].get("file"):
            raise ConfigError('photos.pick is "fixed", so photos.file must name the picture')
        if d["clock"] not in ("12h", "24h"):
            raise ConfigError('clock must be "12h" or "24h"')
        if d["date_order"] not in ("day-month", "month-day"):
            raise ConfigError('date_order must be "day-month" or "month-day"')
        if d["weather"]["units"] not in ("celsius", "fahrenheit"):
            raise ConfigError('weather.units must be "celsius" or "fahrenheit"')
        for b in d["blocks"]:
            if b.get("type") not in BLOCKS:
                raise ConfigError('unknown block "%s" (blocks are %s)' % (b.get("type"), ", ".join(BLOCKS)))
        for r in d["reminders"]:
            if not r.get("text"):
                raise ConfigError("every reminder needs a text")
            for day in r.get("days", []):
                if day.lower()[:3] not in DAY_NAMES:
                    raise ConfigError('reminder day "%s" is not a day (use mon, tue, wed ...)' % day)
        s = d["schedule"]
        if not 0 <= int(s.get("start_hour", 5)) <= 23:
            raise ConfigError("schedule.start_hour must be 0 to 23")
        if int(s.get("every_hours", 0)) < 0:
            raise ConfigError("schedule.every_hours must be 0 (once a day) or more")
        if self.data.get("timezone"):
            try:
                ZoneInfo(self.data["timezone"])
            except Exception:
                raise ConfigError('timezone "%s" is not known (example: "Australia/Melbourne")' % self.data["timezone"])


def load(path=None, required=True):
    """Load config.json (or the file given). With required=False a missing file gives defaults."""
    path = path or os.environ.get("SMARTFRAME_CONFIG") or "config.json"
    if not os.path.exists(path):
        if required:
            raise ConfigError("no settings file at %s (copy config.example.json to config.json first)" % path)
        return Config({}, path)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigError("%s is not valid JSON: line %s, %s" % (path, e.lineno, e.msg))
    data.pop("_comment", None)
    return Config(data, path)
