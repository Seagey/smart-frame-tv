"""The words on the picture: the date, the weather, calendar events, reminders and a line of text.

Only two things ever reach the internet: the weather (Open-Meteo, free, no account, sent only the
latitude and longitude) and your calendar link, if you give one. Both are kept in the data folder
so a picture can still be made when the internet is down for a moment.
"""
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December")
SHORT_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
UA = "smart-frame-tv/0.1 (+https://github.com/Seagey/smart-frame-tv)"

# WMO weather codes, as Open-Meteo reports them, in plain words.
WEATHER = {
    0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Cloudy", 45: "Fog", 48: "Fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle", 56: "Freezing drizzle", 57: "Freezing drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain", 66: "Freezing rain", 67: "Freezing rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Showers", 81: "Showers", 82: "Heavy showers", 85: "Snow showers", 86: "Snow showers",
    95: "Storms", 96: "Storms with hail", 99: "Storms with hail",
}


def _get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


# ---------------------------------------------------------------- date

def date_text(d, order="day-month"):
    if order == "month-day":
        return "%s, %s %d" % (DAYS[d.weekday()], MONTHS[d.month - 1], d.day)
    return "%s %d %s" % (DAYS[d.weekday()], d.day, MONTHS[d.month - 1])


def time_text(t, clock="12h"):
    if clock == "24h":
        return "%02d:%02d" % (t.hour, t.minute)
    h = t.hour % 12 or 12
    return "%d%s %s" % (h, ":%02d" % t.minute if t.minute else "", "am" if t.hour < 12 else "pm")


# ---------------------------------------------------------------- weather

def find_place(cfg):
    """Latitude and longitude for the place in config.json, looked up once by name if needed."""
    p = cfg["place"]
    if p.get("latitude") is not None and p.get("longitude") is not None:
        return float(p["latitude"]), float(p["longitude"]), p.get("name") or ""
    if not p.get("name"):
        raise ValueError("set place.name (a suburb or city) or place.latitude and place.longitude")
    cache = cfg.file("place.json")
    hit = _read_json(cache)
    if hit and hit.get("query") == p["name"]:
        return hit["latitude"], hit["longitude"], hit["name"]
    q = {"name": p["name"].split(",")[0].strip(), "count": 1, "language": "en", "format": "json"}
    if p.get("country"):
        q["countryCode"] = p["country"]
    res = json.loads(_get("https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode(q)))
    if not res.get("results"):
        raise ValueError('could not find "%s"; try a nearby city, or set place.latitude and place.longitude' % p["name"])
    r = res["results"][0]
    _write_json(cache, {"query": p["name"], "latitude": r["latitude"], "longitude": r["longitude"], "name": r["name"]})
    return r["latitude"], r["longitude"], r["name"]


def weather(cfg, today):
    """Today's forecast as {"text", "high", "low", "rain", "place"}, or None if it cannot be had."""
    w = cfg["weather"]
    cache = cfg.file("weather.json")
    try:
        lat, lon, place = find_place(cfg)
        q = {"latitude": round(lat, 3), "longitude": round(lon, 3), "timezone": "auto", "forecast_days": 3,
             "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"}
        if w["units"] == "fahrenheit":
            q["temperature_unit"] = "fahrenheit"
        res = json.loads(_get("https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(q)))
        d = res["daily"]
        i = d["time"].index(today.isoformat()) if today.isoformat() in d["time"] else 0
        out = {"date": today.isoformat(), "code": d["weather_code"][i],
               "text": WEATHER.get(d["weather_code"][i], "Mixed"),
               "high": round(d["temperature_2m_max"][i]), "low": round(d["temperature_2m_min"][i]),
               "rain": d.get("precipitation_probability_max", [None] * (i + 1))[i], "place": place}
        _write_json(cache, out)
        return out
    except Exception as e:
        old = _read_json(cache)
        if old and old.get("date") == today.isoformat():
            return old
        print("weather: not available (%s)" % e)
        return None


def weather_text(wx, cfg):
    if not wx:
        return ""
    unit = "°" if cfg["weather"]["units"] == "celsius" else "°F"
    text = "%s, %d%s and %d%s" % (wx["text"], wx["high"], unit, wx["low"], unit)
    if cfg["weather"].get("rain_chance") and wx.get("rain") is not None and wx["rain"] >= 20:
        text += ", %d%% chance of rain" % wx["rain"]
    if cfg["weather"].get("show_place") and wx.get("place"):
        text = wx["place"] + ": " + text[0].lower() + text[1:]
    return text


# ---------------------------------------------------------------- calendar

def _fetch_calendar(cfg, url):
    url = url.strip()
    scheme, _, rest = url.partition(":")
    if rest.startswith("//") and scheme.lower() not in ("http", "https", "file"):
        url = "https:" + rest   # calendar-app links (Apple's, for one) are the same address over https
    cache = cfg.file("calendar-%s.ics" % hashlib.sha1(url.encode()).hexdigest()[:10])
    try:
        fresh = os.path.exists(cache) and time.time() - os.path.getmtime(cache) < 600
        if not fresh:
            raw = _get(url, timeout=30)
            if b"BEGIN:VCALENDAR" not in raw[:2000]:
                raise ValueError("that link did not give back a calendar (is it the public .ics link?)")
            with open(cache, "wb") as f:
                f.write(raw)
            os.chmod(cache, 0o600)
    except Exception as e:
        if not os.path.exists(cache):
            print("calendar: not available (%s)" % e)
            return None
        print("calendar: using the last copy (%s)" % e)
    with open(cache, "rb") as f:
        return f.read()


def events(cfg, now):
    """Events from today for calendar.days days, as [{"when", "title", "start"}], soonest first."""
    c = cfg["calendar"]
    urls = [u for u in c.get("ics_urls", []) if u]
    if not urls:
        return []
    try:
        import icalendar
        import recurring_ical_events
    except ImportError:
        print("calendar: run pip install -r requirements.txt (icalendar is missing)")
        return []
    tz = cfg.tz
    days = max(1, int(c.get("days", 2)))
    t0 = datetime(now.year, now.month, now.day, tzinfo=tz)
    t_end = t0 + timedelta(days=days)
    hide = [h.lower() for h in c.get("hide", [])]
    found, seen = [], set()
    for url in urls:
        raw = _fetch_calendar(cfg, url)
        if not raw:
            continue
        try:
            cal = icalendar.Calendar.from_ical(raw)
            items = recurring_ical_events.of(cal).between(t0, t_end)
        except Exception as e:
            print("calendar: could not read one calendar (%s)" % e)
            continue
        for ev in items:
            title = str(ev.get("SUMMARY", "")).strip()
            if not title or any(h in title.lower() for h in hide):
                continue
            s = ev.get("DTSTART").dt
            e = ev.get("DTEND").dt if ev.get("DTEND") else s
            all_day = not isinstance(s, datetime)
            if all_day:
                start = datetime(s.year, s.month, s.day, tzinfo=tz)
                end = datetime(e.year, e.month, e.day, tzinfo=tz) if e != s else start + timedelta(days=1)
            else:
                start = (s if s.tzinfo else s.replace(tzinfo=tz)).astimezone(tz)
                end = (e if e.tzinfo else e.replace(tzinfo=tz)).astimezone(tz) if isinstance(e, datetime) else start
            if end <= t0 and not (end == start == t0):
                continue
            key = (title, start.isoformat())
            if key in seen:
                continue
            seen.add(key)
            found.append({"title": title, "start": start, "all_day": all_day})
    found.sort(key=lambda x: (x["start"], not x["all_day"]))
    out = []
    for f in found[: int(c.get("max", 3))]:
        out.append({"when": _when(f, t0, cfg["clock"]), "title": f["title"], "start": f["start"].isoformat()})
    return out


def _when(ev, t0, clock):
    day = (ev["start"].date() - t0.date()).days
    t = "" if ev["all_day"] else time_text(ev["start"], clock)
    if day <= 0:
        return "Today" if (ev["all_day"] or day < 0) else t
    name = "Tomorrow" if day == 1 else DAYS[ev["start"].weekday()]
    return (name + " " + t).strip()


# ---------------------------------------------------------------- reminders and quote

def reminders(cfg, today):
    out = []
    for r in cfg["reminders"]:
        days = [d.lower()[:3] for d in r.get("days", [])]
        if days and SHORT_DAYS[today.weekday()] not in days:
            continue
        every = int(r.get("every_weeks", 1) or 1)
        if every > 1:
            start = date.fromisoformat(r.get("start") or "2000-01-03")
            if ((today - start).days // 7) % every != 0:
                continue
        out.append({"text": r["text"], "dots": r.get("dots", [])})
    return out


def quote(cfg, today):
    q = cfg["quote"]
    lines = [x for x in q.get("lines", []) if x]
    if lines:
        return lines[today.toordinal() % len(lines)]
    return q.get("text", "")


# ---------------------------------------------------------------- everything together

def gather(cfg, now=None, sample=False):
    """Everything the picture needs, in the order the blocks are listed in config.json."""
    if sample:
        return sample_info(cfg)
    now = now or cfg.now()
    today = now.date()
    out = {"blocks": [], "date": "", "weather": "", "events": [], "empty_text": cfg["calendar"].get("empty_text", ""),
           "reminders": [], "quote": ""}
    for b in cfg["blocks"]:
        if not b.get("on", True):
            continue
        kind = b["type"]
        out["blocks"].append(kind)
        if kind == "date":
            out["date"] = date_text(today, cfg["date_order"])
        elif kind == "weather":
            wx = weather(cfg, today)
            out["weather"] = weather_text(wx, cfg)
            if wx:
                out["wx"] = {"text": wx["text"], "high": wx["high"], "low": wx["low"],
                             "unit": "°" if cfg["weather"]["units"] == "celsius" else "°F"}
        elif kind == "calendar":
            out["events"] = events(cfg, now)
        elif kind == "reminders":
            out["reminders"] = reminders(cfg, today)
        elif kind == "quote":
            out["quote"] = quote(cfg, today)
    return out


def sample_info(cfg):
    """Made-up details for previews and the README pictures. Nothing here comes from you."""
    unit = "°" if cfg["weather"]["units"] == "celsius" else "°F"
    hi, lo = (24, 15) if unit == "°" else (75, 59)
    blocks = [b["type"] for b in cfg["blocks"] if b.get("on", True)]
    return {
        "blocks": blocks,
        "date": date_text(date(2026, 3, 3), cfg["date_order"]),
        "weather": "Partly cloudy, %d%s and %d%s" % (hi, unit, lo, unit),
        "wx": {"text": "Partly cloudy", "high": hi, "low": lo, "unit": unit},
        "events": [{"when": time_text(datetime(2026, 3, 3, 9, 30), cfg["clock"]), "title": "Dentist"},
                   {"when": "Tomorrow", "title": "School photos"},
                   {"when": "Tomorrow " + time_text(datetime(2026, 3, 4, 18, 0), cfg["clock"]), "title": "Dinner at the beach"}][: int(cfg["calendar"].get("max", 3))],
        "empty_text": cfg["calendar"].get("empty_text", ""),
        "reminders": [{"text": "Recycling out tonight", "dots": ["#e2b33c", "#4a8a4a"]}],
        "quote": cfg["quote"].get("text") or "Slow mornings are the good ones.",
    }
