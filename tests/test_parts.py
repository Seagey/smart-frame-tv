"""Photo picking, the schedule, reminders, calendars and rendering."""
import os
import shutil
import tempfile
import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

from PIL import Image

from smartframe import cli, config, info, photos, render
from smartframe.state import State

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TZ = ZoneInfo("Australia/Melbourne")

ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//test//EN
BEGIN:VEVENT
UID:1
DTSTART;TZID=Australia/Melbourne:20260303T093000
DTEND;TZID=Australia/Melbourne:20260303T103000
SUMMARY:Dentist
END:VEVENT
BEGIN:VEVENT
UID:2
DTSTART;VALUE=DATE:20260304
DTEND;VALUE=DATE:20260305
SUMMARY:School photos
END:VEVENT
BEGIN:VEVENT
UID:3
DTSTART;TZID=Australia/Melbourne:20260210T180000
DTEND;TZID=Australia/Melbourne:20260210T190000
RRULE:FREQ=WEEKLY;BYDAY=TU
SUMMARY:Swimming
END:VEVENT
BEGIN:VEVENT
UID:4
DTSTART;TZID=Australia/Melbourne:20260310T080000
DTEND;TZID=Australia/Melbourne:20260310T090000
SUMMARY:Next week
END:VEVENT
END:VCALENDAR
"""


class Parts(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="smartframe-test-")
        self.photos = os.path.join(self.dir, "photos")
        os.makedirs(self.photos)
        for n in ("a.jpg", "b.jpg", "c.jpg", "12-25 tree.jpg"):
            Image.new("RGB", (400, 300), (120, 140, 160)).save(os.path.join(self.photos, n))

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def cfg(self, **d):
        base = {"timezone": "Australia/Melbourne", "photos": {"folder": self.photos}}
        base.update(d)
        return config.Config(base, os.path.join(self.dir, "config.json"))

    def test_day_pick_is_steady_and_moves_on(self):
        c, st = self.cfg(), State(os.path.join(self.dir, "s.json"))
        a = photos.choose(c, st, date(2026, 3, 3))
        self.assertEqual(a, photos.choose(c, st, date(2026, 3, 3)))
        self.assertNotEqual(a, photos.choose(c, st, date(2026, 3, 4)))
        self.assertNotIn("12-25 tree.jpg", {photos.choose(c, st, date(2026, 3, d)) for d in range(1, 20)})

    def test_dated_photo_wins_on_its_day(self):
        c, st = self.cfg(), State(os.path.join(self.dir, "s.json"))
        self.assertEqual(photos.choose(c, st, date(2026, 12, 25)), "12-25 tree.jpg")

    def test_rotate_goes_round(self):
        c, st = self.cfg(photos={"folder": self.photos, "pick": "rotate"}), State(os.path.join(self.dir, "s.json"))
        self.assertEqual([photos.choose(c, st, date(2026, 3, 3)) for _ in range(4)], ["a.jpg", "b.jpg", "c.jpg", "a.jpg"])

    def test_prepare_makes_4k_without_metadata(self):
        out = os.path.join(self.dir, "p.jpg")
        im = photos.prepare(os.path.join(self.photos, "a.jpg"), out)
        self.assertEqual(im.size, (3840, 2160))
        with Image.open(out) as saved:
            self.assertFalse(saved.getexif())

    def test_schedule(self):
        c, st = self.cfg(), State(os.path.join(self.dir, "s.json"))
        self.assertFalse(cli.due(c, st, datetime(2026, 3, 3, 4, 59, tzinfo=TZ)))
        self.assertTrue(cli.due(c, st, datetime(2026, 3, 3, 5, 0, tzinfo=TZ)))
        st.mark_run("2026-03-03")
        self.assertFalse(cli.due(c, st, datetime(2026, 3, 3, 23, 0, tzinfo=TZ)))
        c2 = self.cfg(schedule={"start_hour": 6, "every_hours": 3})
        st.data["last_run"] = datetime(2026, 3, 3, 6, 0, tzinfo=TZ).timestamp()
        self.assertFalse(cli.due(c2, st, datetime(2026, 3, 3, 8, 0, tzinfo=TZ)))
        self.assertTrue(cli.due(c2, st, datetime(2026, 3, 3, 9, 0, tzinfo=TZ)))

    def test_reminders_weekly_and_fortnightly(self):
        c = self.cfg(reminders=[{"text": "Bins", "days": ["tue"]},
                                {"text": "Recycling", "days": ["tue"], "every_weeks": 2, "start": "2026-03-03"}])
        self.assertEqual([r["text"] for r in info.reminders(c, date(2026, 3, 3))], ["Bins", "Recycling"])
        self.assertEqual([r["text"] for r in info.reminders(c, date(2026, 3, 10))], ["Bins"])
        self.assertEqual(info.reminders(c, date(2026, 3, 4)), [])

    def test_calendar_today_tomorrow_and_repeats(self):
        ics = os.path.join(self.dir, "cal.ics")
        with open(ics, "w") as f:
            f.write(ICS)
        c = self.cfg(calendar={"ics_urls": ["file://" + ics], "days": 2, "max": 5})
        evs = info.events(c, datetime(2026, 3, 3, 7, 0, tzinfo=TZ))
        self.assertEqual([(e["when"], e["title"]) for e in evs],
                         [("9:30 am", "Dentist"), ("6 pm", "Swimming"), ("Tomorrow", "School photos")])
        c24 = self.cfg(clock="24h", calendar={"ics_urls": ["file://" + ics], "days": 1, "max": 1})
        self.assertEqual(info.events(c24, datetime(2026, 3, 3, 7, 0, tzinfo=TZ))[0]["when"], "09:30")

    def test_dates(self):
        self.assertEqual(info.date_text(date(2026, 3, 3)), "Tuesday 3 March")
        self.assertEqual(info.date_text(date(2026, 3, 3), "month-day"), "Tuesday, March 3")

    def test_bad_config_is_explained(self):
        with self.assertRaises(config.ConfigError):
            self.cfg(style="neon")
        with self.assertRaises(config.ConfigError):
            self.cfg(reminders=[{"text": "x", "days": ["someday"]}])

    def test_pillow_render_for_every_style(self):
        for style in config.STYLES:
            c = self.cfg(style=style)
            out = os.path.join(self.dir, style + ".jpg")
            self.assertEqual(render.render(c, os.path.join(self.photos, "a.jpg"), info.sample_info(c), out, engine="pillow"), "pillow")
            with Image.open(out) as im:
                self.assertEqual(im.size, (3840, 2160))

    @unittest.skipUnless(render.find_chrome(), "Chrome or Chromium is not installed")
    def test_chrome_render_is_4k(self):
        c = self.cfg(style="gallery")
        out = os.path.join(self.dir, "g.png")
        self.assertEqual(render.render(c, os.path.join(REPO, "samples", "photos", "hills.jpg"), info.sample_info(c), out, engine="chrome"), "chrome")
        with Image.open(out) as im:
            self.assertEqual(im.size, (3840, 2160))


if __name__ == "__main__":
    unittest.main()
